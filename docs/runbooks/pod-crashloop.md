# Runbook: pods crash-looping or not ready

Alerts: `KubePodCrashLooping`, `KubeDeploymentReplicasMismatch` (from kube-prometheus-stack).

## Diagnose a crash loop
1. `kubectl describe pod <pod> -n <ns>` — look at Last State, exit code and events.
2. Exit code 137 means OOMKilled: raise the memory limit or fix the leak.
3. `kubectl logs <pod> -n <ns> --previous` shows the logs of the crashed container.
4. Failing readiness probes remove the pod from the Service; check `/readyz` from inside the cluster.

## Kyverno blocked the pod
If pods never get created, check admission: `kubectl get events -n <ns> | grep -i kyverno`.
Policies require resource limits, probes, a non-root user and no `:latest` tags.

# OpenShift KubeAPISever Load balancer Checker
A small tool used to ensure that the `api.<clustername>` and `api-int.<clustername>` domains route to a load balancer which is distributing load somewhat-evenly between all three instances.

This small tool performs 30 requests to the KubeAPIServer endpoint from the KubeConfig defined in either `~/.kube/config`
or `/host/etc/kubernetes/static-pod-resources/kube-apiserver-certs/secrets/node-kubeconfigs/lb-ext.kubeconfig` when running
in a debug container. 

The tool will perform 100 requests to the KubeAPIServer load balancer, inspecting the JSON output responses and 
correlating the requests to the APIServer instance that generated the response. From this, the load spread can be seen
when all load is sent from the same location.

**NOTE:** This must be run on one of the OpenShift Master Nodes and will not work correctly if run on a Worker Node.

## How to use:
The following command can be used to 
``` bash
NODE_NAME=master-0.examplecluster.com
oc debug --image=quay.io/mwasher/api-lb-checker "nodes/${NODE_NAME}" -- python3 /app/app.py
```

## Interpreting the Output:
An example output has been provided below:
```commandline
API Server test output:
-----------------------
API IP          |       Response Count
-----------------------
10.XX.XX.1      |       30
10.XX.XX.2      |       None
10.XX.XX.3      |       None
-----------------------
```

From this output we can see all requests were processed by a single APIServer instance, indicating there is uneven load distribution 
and/or the other APIServer instances may not be functioning correctly.

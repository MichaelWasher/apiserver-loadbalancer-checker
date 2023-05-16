import argparse
import json
import logging
import os
import sys
from collections import defaultdict

import urllib3
from kubernetes import client, config

# NOTE: Mute warnings about invalid Certificate Authorities as this is commonplace in OpenShift
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

APP_NAME = "api-lb-checker"
VERSION = "0.0.1"

# Configure Logging:
file_handler = logging.FileHandler(filename='tmp.log')
stdout_handler = logging.StreamHandler(stream=sys.stdout)
handlers = [file_handler, stdout_handler]

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s',
    handlers=handlers
)


# Configs can be set in Configuration class directly or using helper utility
def setup_kubernetes():
    lb_ext_location = "/host/etc/kubernetes/static-pod-resources/kube-apiserver-certs/secrets/node-kubeconfigs/lb-ext.kubeconfig"
    local_location = os.environ.get('KUBECONFIG', '~/.kube/config').split(":")[0]
    # Running on client
    if os.path.isfile(local_location):
        logging.info('using client-based kubernetes configuration')
        config.load_kube_config()
    # Running in debug Pod on Master
    elif os.path.isfile(lb_ext_location):
        logging.info('using lb-ext.kubeconfig configuration on Master Nodes')
        config.load_kube_config(config_file=lb_ext_location)
    else:
        logging.info('using incluster configuration. WARNING: This will most-likely not provide the desired outcome. '
                     'Review if this is right for your testing.')
        config.load_incluster_config()

    v1 = client.CoreV1Api()
    api_client = v1.api_client
    return api_client, v1


def get_apiserver_ips(v1):
    """

    Returns
    -------

    """
    # kgp -n openshift-kube-apiserver -l app=openshift-kube-apiserver
    ns = "openshift-kube-apiserver"
    label_selector = "app=openshift-kube-apiserver"

    pod_list = v1.list_namespaced_pod(namespace=ns, label_selector=label_selector)

    pod_ips = [pod.status.pod_ip for pod in pod_list.items]
    return pod_ips


def get_apiserver_serveraddress(api_client):
    """

    Parameters
    ----------
    api_client

    Returns
    -------

    """
    # logging.getLogger("urllib3").setLevel(logging.DEBUG) #TODO: Add argument to enable debug for this app. and put this in an if
    
    api_client.rest_client.pool_manager.clear() #HACK: Force the kube api_client to close old connections.
    resp, status_code, headers = api_client.call_api('/api', 'GET', auth_settings=['BearerToken'], response_type='json',
                                                     _preload_content=False)
    api_resp = json.loads(resp.data.decode('utf-8'))
    logging.debug( api_resp )
    api_ip_addresses = [address_tuple["serverAddress"] for address_tuple in api_resp["serverAddressByClientCIDRs"]]
    # Filter any IPs with port numbers
    api_ip_addresses = [ip.split(":")[0] for ip in api_ip_addresses]

    return api_ip_addresses


def display_loadbalancer_check_output(expected_ips, apiserver_ip_counts):
    log_line = "API Server test output:\n-----------------------\nAPI IP\t\t|\tResponse Count\n-----------------------\n"
    for api_ip in expected_ips:
        log_line += f"{api_ip}\t|\t{apiserver_ip_counts.get(api_ip)}\n"
    log_line += "-----------------------"
    logging.info(log_line)


def perform_apiserver_loadbalancer_checks(api_client, v1, retries=100, pass_threshold=0.5):
    """

    Parameters
    ----------
    api_client

    Returns
    -------
    apiserver_ip_counts A dictionary containing APIServer IP addresses and their count

    """
    apiserver_ip_counts = defaultdict(lambda: 0)

    expected_ips = get_apiserver_ips(v1)
    expected_num_of_apiservers = len(expected_ips)
    for i in range(retries):
        for ip in get_apiserver_serveraddress(api_client):
            apiserver_ip_counts[ip] += 1

    # Display
    display_loadbalancer_check_output(expected_ips, apiserver_ip_counts)

    # Check for failures
    if len(apiserver_ip_counts.keys()) < expected_num_of_apiservers:
        raise Exception("Not all expected APIServers were seen in responses. This may indicate sticky sessions.")

    # Warn if pass_threshold is not met
    for api_ip, count in apiserver_ip_counts:
        if count < ((retries / expected_num_of_apiservers) * pass_threshold):
            raise Exception(
                f"APIServers is heavily uneven. Expected {retries / expected_num_of_apiservers} for each IP. Failed on {api_ip}.")

    return apiserver_ip_counts


def parse_args():
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{VERSION} - network configuration debugging tool for OpenShift",
        prog=APP_NAME)

    parser.add_argument("--version", action="store_true",
                        help="Get program version")

    # TODO: Make the API endpoint configurable
    # parser.add_argument("--api-endpoint", "-e", help="The domain name of the API that is tested.",
    #                     default=environ.get(f"{APP_NAME.upper()}_API"))

    return parser.parse_args()


def display_version():
    """ Display the current version of the applications"""
    print(description=f"{APP_NAME} v{VERSION} - network configuration debugging tool for OpenShift")


def __main__():
    # Parse args
    args = parse_args()

    # Deal with Version and help
    if args.version:
        display_version()
        exit(0)

    api_client, v1 = setup_kubernetes()
    try:
        # Check API Service LoadBalancer
        perform_apiserver_loadbalancer_checks(api_client, v1)
    except Exception as e:
        logging.error(e)


__main__()

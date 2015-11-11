#!/usr/bin/python
# Copyright 2016 Google Inc. All Rights Reserved.
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>

DOCUMENTATION = '''
---
module: gke
version_added: "2.1"
short_description: Create and destroy Google Container Engine (GKE) clusters.
description:
    - This module provides create and destroy support for Google Container
      Engine (GKE) clusters. It does not currently provide a mechanism to
      update an existing cluster. This module uses v1 of the the
      GKE API U(https://cloud.google.com/container-engine/reference/rest/)
options:
  name:
    description:
      - Name of the GKE cluster
    required: true
  description:
    description:
      - Description for the GKE cluster
    required: false
  node_count:
    description:
      - Description for the GKE cluster
    required: false
    default: 2
  node_config_machine_type:
    description:
      - The nodeConfig machine type
    required: false
    default: "n1-standard-1"
  node_config_disksize:
    description:
      - The nodeConfig disk size in GB
    required: false
    default: 100
  node_config_scopes:
    description:
      - The nodeConfig list of scopes to set for each node
    required: false
    default: [
        "https://www.googleapis.com/auth/compute",
        "https://www.googleapis.com/auth/devstorage.read_only",
        "https://www.googleapis.com/auth/logging.write",
        "https://www.googleapis.com/auth/monitoring"
        ]
  node_config_metadata:
    description:
      - The nodeConfig metadata to add to each node's instance metadata
    required: false
  username:
    description:
      - The username for accessing the Kubernetes cluster
    required: true
    default: "admin"
  password:
    description:
      - The password for accessing the Kubernetes cluster
    required: true
  logging_service:
    description:
      - The logging service the cluster should write logs to
    required: false
    choices: ["none", "logging.googleapis.com"]
    default: "logging.googleapis.com"
  monitoring_svc:
    description:
      - The monitoring service the cluster should write metrics to
    required: false
    choices: ["none", "monitoring.googleapis.com"]
    default: "monitoring.googleapis.com"
  network_name:
    description:
      - The name of the GCE network to connect the cluster to
    required: false
    default: "default"
  ipv4_range:
    description:
      - The IPv4 CIDR network range to use for the cluster (e.g. 10.96.0.0/14)
    required: false
  credential_file:
    description:
      - Full pathname to Service Account JSON credentials file
    required: true
  project_id:
    description:
      - Google Cloud Platform project id
    required: true
  state:
    description:
      - The desired action to take on the cluster
    required: true
    default: "present"
    choices: ["present", "absent"]
  wait_for:
    description:
      - Wait for (block on) requests to complete. Creating/deleting clusters
        may take several minutes. Set to 'false' to proceed immediately after
        the request is made versus waiting for the request to complete.
    required: false
    default: true
  wait_poll_interval:
    description:
      - Number of seconds between polling for operation completion.
    required: false
    default: 10
  zone:
    description:
      - The zone where the GKE cluster resides.
    required: true

requirements:
    - "google-api-python-client >= 1.4.2"
author: "Eric Johnson (@erjohnso) <erjohnso@google.com>"
'''

EXAMPLES = '''
# Create a GKE cluster
- hosts: localhost
  gather_facts: False
  vars:
    project_id: empyrean-yeti-226
    credential_file: /home/erjohnso/pkey.json
  tasks:
  - name: Create a the GKE cluster
    gke:
        project_id: "{{ project_id }}"
        credential_file: "{{ credential_file }}"
        name: gke-test
        username: erjohnso
        node_count: 3
        node_config_machine_type: n1-standard-1
        node_config_scopes:
            - https://www.googleapis.com/auth/compute
            - https://www.googleapis.com/auth/devstorage.full_control
            - https://www.googleapis.com/auth/logging.write
            - https://www.googleapis.com/auth/monitoring
            - https://www.googleapis.com/auth/datastore
        node_config_metadata:
            key1: value1
            key2: value2
        zone: us-central1-f
        wait_for: false
        state: present
'''

RETURN = '''
    clusterIpv4Cidr: 10.72.0.0/14
    createTime: '2016-01-05T16:22:10+00:00'
    currentMasterVersion: 1.1.3
    currentNodeCount: 2
    currentNodeVersion: 1.1.3
    description: GKE Cluster created with Ansible
    endpoint: 123.45.67.89
    initialClusterVersion: 1.1.3
    initialNodeCount: 2
    instanceGroupUrls:
        - https://www.googleapis.com/.../gke-dev-cluster-2b04fb68-group
    loggingService: logging.googleapis.com
    masterAuth:
        clientCertificate: LS0...S0tCg==
        clientKey: LS0...S0tCg==
        clusterCaCertificate: LS0...tLS0K
        password: correct horse battery staple
        username: erjohnso
    monitoringService: monitoring.googleapis.com
    name: dev-cluster
    network: default
    nodeConfig:
      diskSizeGb: 100
      machineType: n1-standard-1
      oauthScopes:
        - https://www.googleapis.com/auth/compute
        - https://www.googleapis.com/auth/devstorage.read_only
        - https://www.googleapis.com/auth/logging.write
        - https://www.googleapis.com/auth/monitoring
    nodeIpv4CidrSize: 24
    selfLink: https://container.googleapis.com/.../clusters/dev-cluster
    servicesIpv4Cidr: 10.75.240.0/20
    status: RUNNING
    zone: us-central1-f
'''

USER_AGENT = "ansible-gke-module/0.0.1"
from httplib2 import Http
try:
    from oauth2client.client import SignedJwtAssertionCredentials
    from apiclient.discovery import build
    from googleapiclient.http import set_user_agent
    from googleapiclient.errors import HttpError
    HAS_GOOGLE_API_CLIENT = True
except ImportError:
    HAS_GOOGLE_API_CLIENT = False


def _make_cluster_body(module):
    cluster = {}
    cluster['name'] = module.params.get('name')
    if module.params.get('description'):
        cluster['description'] = module.params.get('description')
    cluster['initialNodeCount'] = module.params.get('node_count')
    cluster['nodeConfig'] = {
        'machineType': module.params.get('node_config_machine_type'),
        'diskSizeGb': module.params.get('node_config_disksize'),
        'oauthScopes': module.params.get('node_config_scopes'),
    }
    if module.params.get('node_config_metadata'):
        cluster['nodeConfig']['metadata'] = \
            module.params.get('node_config_metadata')
    cluster['masterAuth'] = {
        'username': module.params.get('username'),
        'password': module.params.get('password')
    }
    if module.params.get('logging_service'):
        cluster['loggingService'] = module.params.get('logging_service')
    if module.params.get('monitoring_svc'):
        cluster['monitoringService'] = module.params.get('monitoring_svc')
    if module.params.get('network_name'):
        cluster['network'] = module.params.get('network_name')
    if module.params.get('ipv4_range'):
        cluster['clusterIpv4Cidr'] = module.params.get('ipv4_range')
    if module.params.get('zone'):
        cluster['zone'] = module.params.get('zone')
    body = {'cluster': cluster}
    return body


def main():
    module = AnsibleModule(
        argument_spec=dict(
            credential_file=dict(required=True),
            project_id=dict(required=True),

            name=dict(required=True),
            description=dict(required=False,
                             default="GKE Cluster created with Ansible"),
            node_count=dict(required=False, default=2),
            node_config_machine_type=dict(required=False,
                                          default="n1-standard-1"),
            node_config_disksize=dict(required=False, default=100),
            node_config_scopes=dict(required=False, default=[
                "https://www.googleapis.com/auth/compute",
                "https://www.googleapis.com/auth/devstorage.read_only",
                "https://www.googleapis.com/auth/logging.write",
                "https://www.googleapis.com/auth/monitoring"
                ]
            ),
            node_config_metadata=dict(required=False),
            username=dict(required=False, default="admin"),
            password=dict(required=True),
            logging_service=dict(required=False,
                                 default="logging.googleapis.com"),
            monitoring_svc=dict(required=False,
                                default="monitoring.googleapis.com"),
            network_name=dict(required=False, default="default"),
            ipv4_range=dict(required=False),
            wait_for=dict(required=False, default=True),
            wait_poll_interval=dict(required=False, default=10),
            zone=dict(required=True),
            state=dict(default="present", choices=["present", "absent"])
        )
    )

    if not HAS_GOOGLE_API_CLIENT:
        module.fail_json(msg='This module requires google-api-python-client.')

    creds_file = open(module.params.get("credential_file"), "r")
    cred_data = json.load(creds_file)
    credentials = SignedJwtAssertionCredentials(cred_data["client_email"],
                                                cred_data["private_key"],
                                                "https://www.googleapis.com/"
                                                "auth/cloud-platform")

    http = Http()
    http = set_user_agent(http, USER_AGENT)
    credentials.authorize(http)
    gke = build("container", "v1", http=http)

    changed = False
    state = module.params.get("state")
    project = module.params.get("project_id")
    zone = module.params.get("zone")
    name = module.params.get("name")
    wait_for = module.params.get("wait_for")
    wait_poll_interval = module.params.get("wait_poll_interval")
    polling = wait_for

    cluster_func = gke.projects().zones().clusters

    if state == "present":
        body = _make_cluster_body(module)
        try:
            resp = cluster_func().create(projectId=project, zone=zone,
                                         body=body).execute()
            resp = cluster_func().get(projectId=project, zone=zone,
                                      clusterId=name).execute()
            changed = True
        except HttpError, e:
            if e.resp.status == 409:
                resp = cluster_func().get(projectId=project, zone=zone,
                                          clusterId=name).execute()
                polling = False
            else:
                raise e

        while polling:
            time.sleep(wait_poll_interval)
            resp = cluster_func().get(projectId=project, zone=zone,
                                      clusterId=name).execute()
            if resp['status'] == 'RUNNING':
                polling = False
            if resp['status'] in ['ERROR', 'STATUS_UNSPECIFIED']:
                module.fail_json(msg="Error [%s]: '%s'" % (resp['status'],
                                 resp['statusMessage']))

        module.exit_json(changed=changed, **resp)

    if state == "absent":
        try:
            resp = cluster_func().delete(projectId=project, zone=zone,
                                         clusterId=name).execute()
            changed = True
        except HttpError, e:
            if e.resp.status == 404:
                polling = False
            else:
                raise e

        while polling:
            time.sleep(wait_poll_interval)
            try:
                resp = cluster_func().get(projectId=project, zone=zone,
                                          clusterId=name).execute()
            except HttpError, e:
                if e.resp.status == 404:
                    polling = False
                else:
                    raise e

        resp = {"name": name, "zone": zone, "status": "FOT FOUND"}
        module.exit_json(changed=changed, **resp)

    module.fail_json(msg="Invalid state: '%s'" % state)


# import module snippets
from ansible.module_utils.basic import *       # NOQA

if __name__ == "__main__":
    main()

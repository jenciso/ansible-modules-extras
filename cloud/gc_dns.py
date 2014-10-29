#!/usr/bin/env python
# Copyright 2014 Google Inc.
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
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: gc_dns
version_added: "1.8"
short_description: Manage Google Cloud DNS resources
description:
     - Manage Google Could DNS resources.
       U(https://cloud.google.com/products/cloud-dns) for an overview.
options:
  command:
    description:
       - the action to take on the specified resource
    required: true
    default: "get"
    choices: ["list", "get", "create", "delete"]
    aliases: []
  description:
    description:
       - one-line description of the zone
    required: false
    default: null
    aliases: []
  dns_name:
    description:
      - the RFC 1034 compliant, DNS zone name being managed
    required: false
    default: null
  name:
    description:
      - the zone name identifier
    required: false
    aliases: ["zone_name", "zone"]
  record:
    description:
      - the full DNS record to create or delete
    required: false
    default: null
    aliases: []
  ttl:
    description:
      - the time-to-live in seconds to cache this record with DNS servers
    required: false
    default: null
    aliases: []
  record_type:
    description:
      - the type of resource record, e.g. A, AAAA, CNAME, MX, etc
    required: false
    default: null
    aliases: []
    choices: ['A','AAAA','CNAME','MX','NS','PTR','SOA','SPF','SRV','TXT']
  value:
    description:
      - comma-separated list of appropriate record data (e.g. IP, DNS name)
    required: false
    default: null
    aliases: []
  pem_file:
    description:
      - path to the pem file associated with the service account email
    required: false
    default: null
    aliases: []
  project_id:
    description:
      - your GCE project ID
    required: false
    default: null
    aliases: []
  service_account_email:
    description:
      - service account email
    required: false
    default: null
    aliases: []

requirements: [ "libcloud" ]
author: Eric Johnson <erjohnso@google.com>
'''

EXAMPLES = '''
# List existing managed zones
- local_action:
    module: gc_dns
    command: list

# List defined records for the specified  managed zone
- local_action:
    module: gc_dns
    command: list
    name: my-example-zone

# Basic example of creating a new managed zone
- local_action:
    module: gc_dns
    command: create
    name: my-example-zone
    dns_name: example.com.
    description: My first managed zone

# Basic example of deleting a managed zone
- local_action:
    module: gc_dns
    command: delete
    name: my-example-zone

# Basic example of adding two 'A' records to an existing zone
- local_action:
    module: gc_dns
    command: create
    zone: my-example-zone
    record: foo.example.com.
    value: 123.45.67.89,98.76.54.32
    record_type: A
    ttl: 7200

# Basic example of deleting an existing record
- local_action:
    module: gc_dns
    command: delete
    zone: my-example-zone
    record: db.example.com.
    record_type: A
    value: 123.45.67.89
'''

import sys

try:
    from libcloud.dns.types import (Provider, ZoneDoesNotExistError,
                                    RecordDoesNotExistError)
    from libcloud.dns.providers import get_driver
    from libcloud.common.google import (GoogleBaseAuthConnection,
                                        ResourceExistsError,
                                        GoogleInstalledAppAuthConnection,
                                        GoogleBaseConnection)
    _ = Provider.GOOGLE
except ImportError:
    print("failed=True " + \
        "msg='libcloud with GCE support >=0.15.0 required for this module'")
    sys.exit(1)

def to_dict(lc_obj):
    """Convert a libcloud object into a dictionary"""
    if type(lc_obj) is list:
        obj_list = []
        for obj in lc_obj:
            out = {}
            out.update(obj.__dict__)
            out.pop("driver", None)
            z = out.get("zone", None)
            if z and type(z) != str: out['zone'] = to_dict(z)
            obj_list.append(out)
        return {'items': obj_list}
    else:
        out = {}
        out.update(lc_obj.__dict__)
        out.pop("driver", None)
        z = out.get("zone", None)
        if z and type(z) != str: out['zone'] = to_dict(z)
        return out


def main():
    module = AnsibleModule(
        argument_spec = dict(
            command = dict(default='get', choices=['list','get','create','delete']),
            description = dict(required=False),
            dns_name = dict(required=False),
            name = dict(required=False),
            record = dict(required=False),
            ttl = dict(required=False),
            record_type = dict(required=False),
            value = dict(required=False),
            pem_file = dict(),
            service_account_email = dict(),
            project_id = dict(),
        )
    )
    conn = gce_connect(module, Provider.GOOGLE)
    # TODO: remove/test after libcloud 0.16.1 goes out
    conn.connection.secure = True
    conn.connection.port = 443

    command = module.params.get('command')
    description = module.params.get('description')
    dns_name = module.params.get('dns_name')
    name = module.params.get('name')
    record = module.params.get('record')
    ttl = module.params.get('ttl')
    record_type = module.params.get('record_type')
    value = module.params.get('value')
    output = {}

    if record and record[-1] != ".":
        module.fail_json(msg="Must specify a valid DNS record name", changed=False)

    if dns_name and dns_name[-1] != ".":
        module.fail_json(msg="Must specify a valid dns_name", changed=False)

    if command == 'list':
        try:
            if name:
                zone = conn.get_zone(name)
                records = []
                for rec in conn.iterate_records(zone):
                    records.append(rec)
                output = to_dict(records)
            else:
                zones = []
                for zone in conn.iterate_zones():
                    zones.append(zone)
                output = to_dict(zones)
        except ZoneDoesNotExistError, e:
            msg="Zone '%s' not found" % (name)
            module.fail_json(msg=msg, changed=False)
        except Exception, e:
            module.fail_json(msg=unexpected_error_msg(e), changed=False)

    elif command == 'get':
        if not name:
            module.fail_json(msg="Missing required 'name'", changed=False)
        if record:
            if not record_type: record_type = "A"
            rec_name = record_type + ":" + record
            try:
                output = to_dict(conn.get_record(name, rec_name))
            except RecordDoesNotExistError, e:
                msg="Record '%s' of type '%s' not found in zone '%s'" % (record, record_type, name)
                module.fail_json(msg=msg, changed=False)
            except Exception, e:
                module.fail_json(msg=unexpected_error_msg(e), changed=False)
        else:
            try:
                output = to_dict(conn.get_zone(name))
            except ZoneDoesNotExistError, e:
                msg="Zone '%s' not found" % (name)
                module.fail_json(msg=msg, changed=False)
            except Exception, e:
                module.fail_json(msg=unexpected_error_msg(e), changed=False)

    elif command == 'create':
        if not name:
            module.fail_json(msg="Missing required 'name'", changed=False)
        if record:
            if not record_type: record_type = "A"
            if not ttl: ttl = 86400
            if not value:
                value = []
            else:
                value = value.split(',')
            data = {
                'ttl': ttl,
                'rrdatas': value,
            }
            try:
                zone = conn.get_zone(u'%s' % name)
                output = to_dict(conn.create_record(record,zone,record_type,data))
                output['changed'] = True
            except ZoneDoesNotExistError, e:
                msg="Zone '%s' not found" % (name)
                module.fail_json(msg=msg, changed=False)
            except Exception, e:
                if e.http_code == 409:
                    rec_name = record_type + ":" + record
                    output = to_dict(conn.get_record(name, rec_name))
                else:
                    module.fail_json(msg=unexpected_error_msg(e), changed=False)
        else:
            if not description:
                description = "Managed zone: %s" % dns_name
            extra = {'name': name, 'description': description}
            try:
                output = to_dict(conn.create_zone(dns_name, extra=extra))
                output['changed'] = True
            # TODO: this should really throw a ResourceAlreadyExists error, but
            #       not available until libcloud 0.16.1 is out
            except Exception, e:
                if e.http_code == 409:
                    zone = conn.get_zone(u'%s' % name)
                    output = to_dict(conn.get_zone(u'%s' % name))
                else:
                    module.fail_json(msg=unexpected_error_msg(e), changed=False)

    elif command == 'delete':
        if not name:
            module.fail_json(msg="Missing required 'name'", changed=False)
        try:
            if record:
                if not record_type: record_type = "A"
                rec_name = record_type + ":" + record
                record_match = conn.get_record(name, rec_name)
                output = to_dict(record_match)
                if not conn.delete_record(record_match):
                    module.fail_json(msg="Failed to delete record %s" % record, changed=False)
                output['changed'] = True
            else:
                zone_match = conn.get_zone(name)
                output = to_dict(zone_match)
                if not conn.delete_zone(zone_match):
                    module.fail_json(msg="Failed to delete zone %s" % name, changed=False)
                output['changed'] = True
        except RecordDoesNotExistError, e:
            # OK that this is already absent, supports idempotency
            output['record'] = record
            output['record_type'] = record_type
            output['name'] = name
        except ZoneDoesNotExistError, e:
            # OK that this is already absent, supports idempotency
            output['name'] = name
        except Exception, e:
            if e.http_code == 404:
                pass
            else:
                module.fail_json(msg=unexpected_error_msg(e), changed=False)

    else:
        module.fail_json(msg="Unknown command '%s', must be 'list', 'get', 'create', or 'delete'." % command,
                changed=False)

    output['command'] = command
    if 'changed' not in output:
        output['changed'] = False
    print json.dumps(output)
    sys.exit(0)

# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.gce import *

main()

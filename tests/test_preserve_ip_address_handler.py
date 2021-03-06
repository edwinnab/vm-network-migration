# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Test roll_back_original_instance() function
"""

import json
import os
from unittest import mock

import google.auth.credentials
import httplib2
import unittest2 as unittest
from googleapiclient.discovery import build
from googleapiclient.http import HttpMock
from googleapiclient.http import RequestMockBuilder
from vm_network_migration.vm_network_migration import *

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def datafile(filename):
    """Generate path of the file
    Args:
        filename: file name

    Returns: the file path

    """
    return os.path.join(DATA_DIR, filename)


def read_json_file(filename):
    """Read *.json file
    Args:
        filename: json file name

    Returns: a Python object

    """
    with open(datafile(filename)) as f:
        res = json.load(f)
        f.close()
    return res


class PreserveIPAddressHandler(unittest.TestCase):
    MOCK_CREDENTIALS = mock.Mock(spec=google.auth.credentials.Credentials)
    compute = discovery.build('compute', 'v1',
                              credentials=MOCK_CREDENTIALS)
    project = "mock_project"
    zone = "mock_us_central1_a"
    region = "mock_us_central1"
    original_instance = "mock_instance_legacy"
    new_instance = "mock_instance_new"
    http = HttpMock(datafile("compute_rest.json"), {
        "status": "200"})
    external_ip_address_body = {
        "name": "example-external-address",
        "address": "35.203.14.22"
    }
    alreadyExistsResponse = httplib2.Response({
        "status": 400,
        "reason": "HttpMock response: the IP address already exists"})
    staticIPNameExistsResponse = httplib2.Response({
        "status": 400,
        "reason": "HttpMock response: the IP's name already exists"
    })
    otherErrorResponse = httplib2.Response({
        "status": 404,
        "reason": "HttpMock response: invalid request"
    })
    successResponse = httplib2.Response({
        "status": 200,
        "reason": "HttpMock response: Successful"
    })
    new_network_info = {
        "network": "https://www.googleapis.com/compute/v1/projects/mock_project/global/networks/mock_target_network",
        "subnetwork": "https://www.googleapis.com/compute/v1/projects/mock_project/regions/us-central1/subnetworks/mock_target_subnetwork"
    }

    def test_not_preserve_external_ip(self):
        request_builder = RequestMockBuilder(
            {
                "compute.addresses.insert": (
                    self.successResponse, '{"name": "bar"}'),
                "compute.regionOperations.get":(
                    self.successResponse, '{"status":"DONE"}')})
        compute = build("compute", "v1", self.http,
                        requestBuilder=request_builder)
        original_instance_template = read_json_file(
            "sample_instance_template.json")
        original_network_interface = original_instance_template["networkInterfaces"][0]
        new_network_interface = preserve_ip_addresses_handler(compute,
                                                              self.project,
                                                              self.new_instance,
                                                              self.new_network_info,
                                                              original_network_interface,
                                                              self.region,
                                                              False)
        self.assertEqual(new_network_interface["network"],
                         self.new_network_info["network"])
        self.assertEqual(new_network_interface["subnetwork"],
                         self.new_network_info["subnetwork"])
        # external IP is ephemeral
        self.assertFalse("accessConfigs" in new_network_interface)
        # internal IP is ephemeral
        self.assertFalse("networkIP" in new_network_interface)

    def test_preserve_external_ip_without_http_error(self):
        request_builder = RequestMockBuilder(
            {
                "compute.addresses.insert": (
                    self.successResponse, '{"name": "bar"}'),
                "compute.regionOperations.get":(
                    self.successResponse, '{"status":"DONE"}')})
        compute = build("compute", "v1", self.http,
                        requestBuilder=request_builder)
        original_instance_template = read_json_file(
            "sample_instance_template.json")
        original_network_interface = original_instance_template["networkInterfaces"][0]
        new_network_interface = preserve_ip_addresses_handler(compute,
                                                              self.project,
                                                              self.new_instance,
                                                              self.new_network_info,
                                                              original_network_interface,
                                                              self.region, True)
        self.assertEqual(new_network_interface["network"],
                         self.new_network_info["network"])
        self.assertEqual(new_network_interface["subnetwork"],
                         self.new_network_info["subnetwork"])
        # external IP is unchanged
        self.assertEqual(new_network_interface["accessConfigs"],
                         original_network_interface["accessConfigs"])
        # internal IP is ephemeral
        self.assertFalse("networkIP" in new_network_interface)

    def test_preserve_an_existing_static_external_ip(self, *mocks):

        request_builder = RequestMockBuilder(
            {
                "compute.addresses.insert": (
                    self.alreadyExistsResponse, b''),
                "compute.regionOperations.get":(
                    self.successResponse, '{"status":"DONE"}')})
        compute = build("compute", "v1", self.http,
                        requestBuilder=request_builder)
        original_instance_template = read_json_file(
            "sample_instance_template.json")
        original_network_interface = original_instance_template["networkInterfaces"][0]
        new_network_interface = preserve_ip_addresses_handler(compute,
                                                              self.project,
                                                              self.new_instance,
                                                              self.new_network_info,
                                                              original_network_interface,
                                                              self.region, True)
        self.assertEqual(new_network_interface["network"],
                         self.new_network_info["network"])
        self.assertEqual(new_network_interface["subnetwork"],
                         self.new_network_info["subnetwork"])
        # external IP is unchanged
        self.assertEqual(new_network_interface["accessConfigs"],
                         original_network_interface["accessConfigs"])
        # internal IP is ephemeral
        self.assertFalse("networkIP" in new_network_interface)

    def test_preserve_an_existing_static_ip_name(self):
        # No error raises, and the original external IP will be used
        # in the new instance template

        request_builder = RequestMockBuilder(
            {
                "compute.addresses.insert": (
                    self.staticIPNameExistsResponse, b''),
                "compute.regionOperations.get": (
                    self.successResponse, '{"status":"DONE"}')})
        compute = build("compute", "v1", self.http,
                        requestBuilder=request_builder)
        original_instance_template = read_json_file(
            "sample_instance_template.json")
        original_network_interface = original_instance_template["networkInterfaces"][0]
        new_network_interface = preserve_ip_addresses_handler(compute,
                                                              self.project,
                                                              self.new_instance,
                                                              self.new_network_info,
                                                              original_network_interface,
                                                              self.region, True)
        self.assertEqual(new_network_interface["network"],
                         self.new_network_info["network"])
        self.assertEqual(new_network_interface["subnetwork"],
                         self.new_network_info["subnetwork"])
        # external IP is unchanged
        self.assertEqual(new_network_interface["accessConfigs"],
                         original_network_interface["accessConfigs"])
        # internal IP is ephemeral
        self.assertFalse("networkIP" in new_network_interface)

    def test_other_http_error(self):
        # No error raises, and the original external IP will be used
        # in the new instance template
        request_builder = RequestMockBuilder(
            {
                "compute.addresses.insert": (
                    self.otherErrorResponse, b''),
                "compute.regionOperations.get": (
                    self.successResponse, '{"status":"DONE"}')})
        compute = build("compute", "v1", self.http,
                        requestBuilder=request_builder)
        original_instance_template = read_json_file(
            "sample_instance_template.json")
        original_network_interface = original_instance_template["networkInterfaces"][0]
        new_network_interface = preserve_ip_addresses_handler(compute,
                                                              self.project,
                                                              self.new_instance,
                                                              self.new_network_info,
                                                              original_network_interface,
                                                              self.region, True)
        self.assertEqual(new_network_interface["network"],
                         self.new_network_info["network"])
        self.assertEqual(new_network_interface["subnetwork"],
                         self.new_network_info["subnetwork"])
        # external IP is ephemeral
        self.assertFalse("accessConfigs" in new_network_interface)
        # internal IP is ephemeral
        self.assertFalse("networkIP" in new_network_interface)

    def test_no_natIP_exists_in_original_vm(self):
        # No error raises, and the original external IP will be used
        # in the new instance template
        original_instance_template = read_json_file(
            "sample_instance_template_no_natIP.json")
        original_network_interface = original_instance_template["networkInterfaces"][0]
        new_network_interface = preserve_ip_addresses_handler(self.compute,
                                                              self.project,
                                                              self.new_instance,
                                                              self.new_network_info,
                                                              original_network_interface,
                                                              self.region, True)
        self.assertEqual(new_network_interface["network"],
                         self.new_network_info["network"])
        self.assertEqual(new_network_interface["subnetwork"],
                         self.new_network_info["subnetwork"])
        # external IP is ephemeral
        self.assertFalse("natIP" in new_network_interface["accessConfigs"])
        # internal IP is ephemeral
        self.assertFalse("networkIP" in new_network_interface)

    def test_no_external_ip_exists_in_original_vm(self):
        # No error raises, and the original external IP will be used
        # in the new instance template
        original_instance_template = read_json_file(
            "sample_instance_template_no_external_ip.json")
        original_network_interface = original_instance_template["networkInterfaces"][0]
        new_network_interface = preserve_ip_addresses_handler(self.compute,
                                                              self.project,
                                                              self.new_instance,
                                                              self.new_network_info,
                                                              original_network_interface,
                                                              self.region, True)
        self.assertEqual(new_network_interface["network"],
                         self.new_network_info["network"])
        self.assertEqual(new_network_interface["subnetwork"],
                         self.new_network_info["subnetwork"])
        # external IP is ephemeral
        self.assertFalse("accessConfigs" in new_network_interface)
        # internal IP is ephemeral
        self.assertFalse("networkIP" in new_network_interface)
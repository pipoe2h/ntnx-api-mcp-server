"""Unit tests for OpenAPI YAML parser."""

from __future__ import annotations

from pathlib import Path

from src.parsers import OpenAPIParser


def test_extract_get_operations_reads_path_and_operation_parameters(tmp_path: Path) -> None:
    yaml_text = """
openapi: 3.0.0
paths:
  /vms/{vmId}:
    parameters:
      - name: vmId
        in: path
        required: true
        schema:
          type: string
    get:
      operationId: getVmById
      summary: Get VM
      x-permissions:
        operationName: View VM
        roleList:
          - name: Prism Viewer
          - name: Prism Admin
      parameters:
        - name: includeStats
          in: query
          required: false
          schema:
            type: boolean
    post:
      operationId: createVm
      summary: Create VM
      requestBody:
        content:
          application/json:
            schema:
              type: object
"""
    file_path = tmp_path / "vmm-v4.2-all-documentation.yaml"
    file_path.write_text(yaml_text, encoding="utf-8")

    parser = OpenAPIParser(file_path)
    parser.load()
    operations = parser.extract_get_operations(namespace="vmm")

    assert len(operations) == 1
    operation = operations[0]
    assert operation.namespace == "vmm"
    assert operation.operation_id == "getVmById"
    assert operation.method == "GET"
    assert operation.path == "/vms/{vmId}"
    assert {parameter.name for parameter in operation.parameters} == {"vmId", "includeStats"}
    assert operation.permissions is not None
    assert operation.permissions.get("operationName") == "View VM"
    assert operation.required_roles == ["Prism Viewer", "Prism Admin"]

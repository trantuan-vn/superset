# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

from superset.portal_rls.attributes import (
    dept_from_role_names,
    resolve_dept_code,
    resolve_tenant_slug,
    tenant_from_username,
)


def test_resolve_tenant_from_username() -> None:
    assert (
        resolve_tenant_slug("t_demo-corp__user@demo-corp", [])
        == "demo-corp"
    )


def test_resolve_dept_empty_for_cntt() -> None:
    roles = ["t_demo-corp_cntt_ld", "t_demo-corp_cntt_cv"]
    assert resolve_dept_code(roles) == ""


def test_resolve_dept_for_department_role() -> None:
    roles = ["t_demo-corp_d_KETOAN_cv"]
    assert resolve_dept_code(roles) == "KETOAN"


def test_inactive_role_suffix_still_parses() -> None:
    assert tenant_from_username("t_acme__bob") == "acme"
    assert dept_from_role_names(["t_acme_d_SALE_ld__inactive"]) == "SALE"

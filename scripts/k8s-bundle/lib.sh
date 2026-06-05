#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

kbundle_die() {
  echo "ERROR: $*" >&2
  exit 1
}

kbundle_require_cmd() {
  command -v "$1" >/dev/null 2>&1 || kbundle_die "Thiếu lệnh '$1'."
}

# Đọc giá trị từ state file: kbundle_state_get KEY
kbundle_state_get() {
  local key="$1"
  local file="$2"
  if [[ -f "${file}" ]]; then
    grep -E "^${key}=" "${file}" 2>/dev/null | tail -1 | cut -d= -f2-
  fi
}

# Ghi/cập nhật key trong state file
kbundle_state_set() {
  local key="$1"
  local value="$2"
  local file="$3"
  touch "${file}"
  if grep -qE "^${key}=" "${file}" 2>/dev/null; then
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' "s|^${key}=.*|${key}=${value}|" "${file}"
    else
      sed -i "s|^${key}=.*|${key}=${value}|" "${file}"
    fi
  else
    echo "${key}=${value}" >> "${file}"
  fi
}

# Kiểm tra image đã có trong docker local
kbundle_image_exists_local() {
  docker image inspect "$1" >/dev/null 2>&1
}

# So sánh version đã deploy với bundle hiện tại
# Trả về 0 nếu GIỐNG NHAU (skip), 1 nếu KHÁC (cần xử lý)
kbundle_version_unchanged() {
  local state_key="$1"
  local current_value="$2"
  local state_file="$3"
  local previous
  previous="$(kbundle_state_get "${state_key}" "${state_file}")"
  [[ -n "${previous}" && "${previous}" == "${current_value}" ]]
}

# Load + push một image từ tar nếu version thay đổi (không ghi state — ghi sau khi deploy OK)
kbundle_load_push_image() {
  local role="$1"
  local full_image="$2"
  local tar_path="$3"
  local state_key="$4"
  local state_file="$5"
  local skip_push="$6"

  [[ -f "${tar_path}" ]] || kbundle_die "Không tìm thấy tar: ${tar_path}"

  if kbundle_version_unchanged "${state_key}" "${full_image}" "${state_file}" \
    && kbundle_image_exists_local "${full_image}"; then
    echo "  [SKIP] ${role}: ${full_image} (version không đổi)"
    return 0
  fi

  echo "  [LOAD] ${role}: ${tar_path}"
  docker load -i "${tar_path}"

  if [[ "${skip_push}" == "true" ]]; then
    echo "  [SKIP PUSH] ${full_image}"
  else
    echo "  [PUSH] ${full_image}"
    docker push "${full_image}"
  fi
}

# Ghi snapshot toàn bộ version sau deploy thành công
kbundle_save_deploy_state() {
  local state_file="$1"
  shift
  while [[ $# -ge 2 ]]; do
    kbundle_state_set "$1" "$2" "${state_file}"
    shift 2
  done
}

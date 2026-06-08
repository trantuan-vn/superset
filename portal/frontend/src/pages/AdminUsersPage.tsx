/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import type { TableColumnsType } from 'antd';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError, type SystemRole } from '@/api/auth';
import { fetchDepartments } from '@/api/departments';
import {
  assignDeptRole,
  createUser,
  fetchUsers,
  removeDeptRole,
  setUserPassword,
  updateUser,
  type DeptRole,
  type PortalUser,
  type UserStatus,
} from '@/api/users';
import { PageHeader } from '@/components/PageHeader';
import {
  canAssignSystemRole,
  canModifyUser,
  permissionContextFromUser,
} from '@/features/auth/permissions';
import { useAuth } from '@/features/auth/useAuth';

const USERS_KEY = ['admin', 'users'] as const;
const DEPARTMENTS_KEY = ['admin', 'departments'] as const;

const ASSIGNABLE_ROLES: SystemRole[] = [
  'dept_user',
  'cntt_chuyenvien',
  'cntt_lanhdao',
  'tenant_admin',
];

interface CreateUserFormValues {
  username: string;
  email: string;
  display_name: string;
  password: string;
  system_role: SystemRole;
  department_id?: string;
  dept_role?: DeptRole;
}

interface EditUserFormValues {
  display_name: string;
  email: string;
  status: UserStatus;
}

interface AssignFormValues {
  department_id: string;
  role: DeptRole;
}

interface SetPasswordFormValues {
  password: string;
  confirm_password: string;
}

export function AdminUsersPage() {
  const { t } = useTranslation();
  const { user: currentUser, isAuthenticated } = useAuth();
  const actorCtx = currentUser
    ? permissionContextFromUser(currentUser)
    : null;
  const creatableRoles = ASSIGNABLE_ROLES.filter((role) =>
    actorCtx ? canAssignSystemRole(actorCtx, role) : false,
  );
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<PortalUser | null>(null);
  const [assignTarget, setAssignTarget] = useState<PortalUser | null>(null);
  const [deactivateTarget, setDeactivateTarget] = useState<PortalUser | null>(null);
  const [passwordTarget, setPasswordTarget] = useState<PortalUser | null>(null);
  const [createForm] = Form.useForm<CreateUserFormValues>();
  const [editForm] = Form.useForm<EditUserFormValues>();
  const [assignForm] = Form.useForm<AssignFormValues>();
  const [passwordForm] = Form.useForm<SetPasswordFormValues>();

  const createSystemRole = Form.useWatch('system_role', createForm);

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: [...USERS_KEY, search],
    queryFn: () => fetchUsers({ search: search || undefined }),
    enabled: isAuthenticated,
  });

  const { data: departments } = useQuery({
    queryKey: DEPARTMENTS_KEY,
    queryFn: () => fetchDepartments({ status: 'active' }),
    enabled: isAuthenticated,
  });

  const invalidateUsers = () => {
    void queryClient.invalidateQueries({ queryKey: USERS_KEY });
  };

  const createMutation = useMutation({
    mutationFn: async (values: CreateUserFormValues) => {
      const { department_id, dept_role, ...userPayload } = values;
      const created = await createUser(userPayload);
      if (
        userPayload.system_role === 'dept_user' &&
        department_id &&
        dept_role
      ) {
        return assignDeptRole(created.id, {
          department_id,
          role: dept_role,
        });
      }
      return created;
    },
    onSuccess: () => {
      message.success(t('adminUsers.created'));
      setCreateOpen(false);
      createForm.resetFields();
      invalidateUsers();
    },
    onError: (err: Error) => {
      message.error(
        err instanceof ApiError ? err.message : t('adminUsers.createError'),
      );
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: EditUserFormValues;
    }) => updateUser(id, payload),
    onSuccess: () => {
      message.success(t('adminUsers.updated'));
      setEditTarget(null);
      editForm.resetFields();
      invalidateUsers();
    },
    onError: (err: Error) => {
      message.error(
        err instanceof ApiError ? err.message : t('adminUsers.updateError'),
      );
    },
  });

  const assignMutation = useMutation({
    mutationFn: ({
      userId,
      payload,
    }: {
      userId: string;
      payload: { department_id: string; role: DeptRole };
    }) => assignDeptRole(userId, payload),
    onSuccess: () => {
      message.success(t('adminUsers.assigned'));
      setAssignTarget(null);
      assignForm.resetFields();
      invalidateUsers();
    },
    onError: (err: Error) => {
      message.error(
        err instanceof ApiError ? err.message : t('adminUsers.assignError'),
      );
    },
  });

  const passwordMutation = useMutation({
    mutationFn: ({
      userId,
      password,
    }: {
      userId: string;
      password: string;
    }) => setUserPassword(userId, password),
    onSuccess: () => {
      message.success(t('adminUsers.passwordUpdated'));
      setPasswordTarget(null);
      passwordForm.resetFields();
    },
    onError: (err: Error) => {
      message.error(
        err instanceof ApiError ? err.message : t('adminUsers.setPasswordError'),
      );
    },
  });

  const removeMutation = useMutation({
    mutationFn: ({
      userId,
      departmentId,
    }: {
      userId: string;
      departmentId: string;
    }) => removeDeptRole(userId, departmentId),
    onSuccess: () => {
      message.success(t('adminUsers.removed'));
      invalidateUsers();
    },
    onError: (err: Error) => {
      message.error(
        err instanceof ApiError ? err.message : t('adminUsers.removeError'),
      );
    },
  });

  const roleLabel = (role: SystemRole) => t(`adminUsers.systemRole.${role}`);

  const deptRoleLabel = (role: DeptRole) =>
    role === 'chuyenvien'
      ? t('adminUsers.deptRole.chuyenvien')
      : t('adminUsers.deptRole.lanhdao');

  const statusLabel = (status: UserStatus) => {
    if (status === 'active') {
      return t('adminUsers.statusActive');
    }
    if (status === 'inactive') {
      return t('adminUsers.statusInactive');
    }
    return t('adminUsers.statusLocked');
  };

  const openEdit = (record: PortalUser) => {
    setEditTarget(record);
    editForm.setFieldsValue({
      display_name: record.display_name,
      email: record.email,
      status: record.status,
    });
  };

  const openSetPassword = (record: PortalUser) => {
    setPasswordTarget(record);
    passwordForm.resetFields();
  };

  const openAssign = (record: PortalUser) => {
    setAssignTarget(record);
    if (record.departments[0]) {
      assignForm.setFieldsValue({
        department_id: record.departments[0].department_id,
        role: record.departments[0].role,
      });
    } else {
      assignForm.resetFields();
    }
  };

  const confirmDeactivate = () => {
    if (!deactivateTarget) {
      return;
    }
    updateMutation.mutate(
      {
        id: deactivateTarget.id,
        payload: {
          display_name: deactivateTarget.display_name,
          email: deactivateTarget.email,
          status: 'inactive',
        },
      },
      {
        onSuccess: () => {
          setDeactivateTarget(null);
          message.success(t('adminUsers.deactivated'));
        },
      },
    );
  };

  const columns: TableColumnsType<PortalUser> = useMemo(
    () => [
      {
        title: t('adminUsers.displayName'),
        dataIndex: 'display_name',
        sorter: (a, b) => a.display_name.localeCompare(b.display_name),
      },
      {
        title: t('adminUsers.email'),
        dataIndex: 'email',
      },
      {
        title: t('adminUsers.systemRoleLabel'),
        dataIndex: 'system_role',
        render: (role: SystemRole) => <Tag>{roleLabel(role)}</Tag>,
        filters: ASSIGNABLE_ROLES.map((role) => ({
          text: roleLabel(role),
          value: role,
        })),
        onFilter: (value, record) => record.system_role === value,
      },
      {
        title: t('adminUsers.statusLabel'),
        dataIndex: 'status',
        render: (status: UserStatus) => (
          <Tag
            color={
              status === 'active' ? 'green' : status === 'locked' ? 'red' : 'default'
            }
          >
            {statusLabel(status)}
          </Tag>
        ),
      },
      {
        title: t('adminUsers.departments'),
        key: 'departments',
        render: (_, record) =>
          record.system_role === 'dept_user' ? (
            record.departments.length > 0 ? (
              <Space direction="vertical" size={2}>
                {record.departments.map((dept) => (
                  <Space key={dept.department_id} size="small">
                    <Tag color="blue">
                      {dept.department_code} — {deptRoleLabel(dept.role)}
                    </Tag>
                    {actorCtx && canModifyUser(actorCtx, record) ? (
                      <Button
                        type="link"
                        size="small"
                        danger
                        onClick={() =>
                          removeMutation.mutate({
                            userId: record.id,
                            departmentId: dept.department_id,
                          })
                        }
                      >
                        {t('adminUsers.removeAssignment')}
                      </Button>
                    ) : null}
                  </Space>
                ))}
              </Space>
            ) : (
              <Typography.Text type="secondary">
                {t('adminUsers.noDepartment')}
              </Typography.Text>
            )
          ) : (
            <Typography.Text type="secondary">—</Typography.Text>
          ),
      },
      {
        title: t('adminUsers.actions'),
        key: 'actions',
        width: 280,
        render: (_, record) => {
          const editable =
            actorCtx !== null && canModifyUser(actorCtx, record);
          return (
            <Space wrap size="small">
              {editable ? (
                <Button type="link" size="small" onClick={() => openEdit(record)}>
                  {t('adminUsers.edit')}
                </Button>
              ) : null}
              {editable ? (
                <Button
                  type="link"
                  size="small"
                  onClick={() => openSetPassword(record)}
                >
                  {t('adminUsers.setPassword')}
                </Button>
              ) : null}
              {editable && record.system_role === 'dept_user' ? (
                <Button type="link" size="small" onClick={() => openAssign(record)}>
                  {t('adminUsers.assignDepartment')}
                </Button>
              ) : null}
              {editable && record.status === 'active' ? (
                <Button
                  type="link"
                  size="small"
                  danger
                  onClick={() => setDeactivateTarget(record)}
                >
                  {t('adminUsers.deactivate')}
                </Button>
              ) : editable && record.status === 'inactive' ? (
                <Button
                  type="link"
                  size="small"
                  onClick={() =>
                    updateMutation.mutate({
                      id: record.id,
                      payload: {
                        display_name: record.display_name,
                        email: record.email,
                        status: 'active',
                      },
                    })
                  }
                >
                  {t('adminUsers.reactivate')}
                </Button>
              ) : null}
              {!editable ? (
                <Typography.Text type="secondary">—</Typography.Text>
              ) : null}
            </Space>
          );
        },
      },
    ],
    [t, actorCtx, removeMutation, updateMutation],
  );

  const deptSelectOptions = (departments ?? []).map((dept) => ({
    value: dept.id,
    label: `${dept.code} — ${dept.name}`,
  }));

  return (
    <>
      <PageHeader
        title={t('adminUsers.title')}
        subtitle={t('adminUsers.subtitle')}
        extra={
          <Button type="primary" onClick={() => setCreateOpen(true)}>
            {t('adminUsers.create')}
          </Button>
        }
      />

      {error ? (
        <Alert
          type="error"
          showIcon
          message={t('adminUsers.loadError')}
          description={
            error instanceof ApiError
              ? error.message
              : t('adminUsers.loadErrorHint')
          }
          action={
            <Button
              size="small"
              loading={isFetching}
              onClick={() => {
                void refetch();
              }}
            >
              {t('adminUsers.retry')}
            </Button>
          }
          style={{ marginBottom: 16 }}
        />
      ) : null}

      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Input.Search
          allowClear
          placeholder={t('adminUsers.searchPlaceholder')}
          onSearch={setSearch}
          style={{ maxWidth: 360 }}
        />

        <Table<PortalUser>
          rowKey="id"
          loading={isLoading}
          columns={columns}
          dataSource={data ?? []}
          scroll={{ x: 960 }}
        />
      </Space>

      {/* Create */}
      <Drawer
        title={t('adminUsers.createTitle')}
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        width={440}
        extra={
          <Space>
            <Button onClick={() => setCreateOpen(false)}>
              {t('adminUsers.cancel')}
            </Button>
            <Button
              type="primary"
              loading={createMutation.isPending}
              onClick={() => {
                void createForm.validateFields().then((values) => {
                  createMutation.mutate(values);
                });
              }}
            >
              {t('adminUsers.save')}
            </Button>
          </Space>
        }
      >
        <Form
          form={createForm}
          layout="vertical"
          initialValues={{ system_role: 'dept_user', dept_role: 'chuyenvien' }}
        >
          <Form.Item
            name="display_name"
            label={t('adminUsers.displayName')}
            rules={[{ required: true, message: t('adminUsers.displayNameRequired') }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="email"
            label={t('adminUsers.email')}
            rules={[
              { required: true, message: t('adminUsers.emailRequired') },
              { type: 'email', message: t('adminUsers.emailInvalid') },
            ]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="username"
            label={t('adminUsers.username')}
            rules={[{ required: true, message: t('adminUsers.usernameRequired') }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="password"
            label={t('adminUsers.password')}
            rules={[
              { required: true, message: t('adminUsers.passwordRequired') },
              { min: 8, message: t('adminUsers.passwordMin') },
            ]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            name="system_role"
            label={t('adminUsers.systemRoleLabel')}
            rules={[{ required: true }]}
          >
            <Select
              options={creatableRoles.map((role) => ({
                value: role,
                label: roleLabel(role),
                title: t(`adminUsers.systemRoleDesc.${role}`),
              }))}
            />
          </Form.Item>
          {createSystemRole ? (
            <Typography.Paragraph type="secondary" style={{ marginTop: -8 }}>
              {t(`adminUsers.systemRoleDesc.${createSystemRole}`)}
            </Typography.Paragraph>
          ) : null}
          {createSystemRole === 'dept_user' ? (
            <>
              <Typography.Text strong>{t('adminUsers.assignSection')}</Typography.Text>
              <Form.Item
                name="department_id"
                label={t('adminUsers.department')}
                rules={[
                  { required: true, message: t('adminUsers.departmentRequired') },
                ]}
              >
                <Select
                  showSearch
                  optionFilterProp="label"
                  options={deptSelectOptions}
                  placeholder={t('adminUsers.departmentPlaceholder')}
                />
              </Form.Item>
              <Form.Item
                name="dept_role"
                label={t('adminUsers.deptRoleLabel')}
                rules={[{ required: true }]}
              >
                <Select
                  options={[
                    {
                      value: 'chuyenvien',
                      label: t('adminUsers.deptRole.chuyenvien'),
                    },
                    { value: 'lanhdao', label: t('adminUsers.deptRole.lanhdao') },
                  ]}
                />
              </Form.Item>
            </>
          ) : null}
          <Typography.Paragraph type="secondary">
            {t('adminUsers.deptPolicyHint')}
          </Typography.Paragraph>
        </Form>
      </Drawer>

      {/* Edit */}
      <Drawer
        title={t('adminUsers.editTitle', { name: editTarget?.display_name })}
        open={Boolean(editTarget)}
        onClose={() => setEditTarget(null)}
        width={440}
        extra={
          <Space>
            <Button onClick={() => setEditTarget(null)}>
              {t('adminUsers.cancel')}
            </Button>
            <Button
              type="primary"
              loading={updateMutation.isPending}
              onClick={() => {
                void editForm.validateFields().then((values) => {
                  if (!editTarget) {
                    return;
                  }
                  updateMutation.mutate({ id: editTarget.id, payload: values });
                });
              }}
            >
              {t('adminUsers.editSave')}
            </Button>
          </Space>
        }
      >
        <Form form={editForm} layout="vertical">
          <Form.Item label={t('adminUsers.username')}>
            <Input value={editTarget?.username} disabled />
          </Form.Item>
          <Form.Item
            name="display_name"
            label={t('adminUsers.displayName')}
            rules={[{ required: true, message: t('adminUsers.displayNameRequired') }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="email"
            label={t('adminUsers.email')}
            rules={[
              { required: true, message: t('adminUsers.emailRequired') },
              { type: 'email', message: t('adminUsers.emailInvalid') },
            ]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="status" label={t('adminUsers.statusLabel')}>
            <Select
              options={[
                { value: 'active', label: t('adminUsers.statusActive') },
                { value: 'inactive', label: t('adminUsers.statusInactive') },
              ]}
            />
          </Form.Item>
        </Form>
      </Drawer>

      {/* Assign department */}
      <Drawer
        title={t('adminUsers.assignTitle', { name: assignTarget?.display_name })}
        open={Boolean(assignTarget)}
        onClose={() => setAssignTarget(null)}
        width={440}
        extra={
          <Space>
            <Button onClick={() => setAssignTarget(null)}>
              {t('adminUsers.cancel')}
            </Button>
            <Button
              type="primary"
              loading={assignMutation.isPending}
              onClick={() => {
                void assignForm.validateFields().then((values) => {
                  if (!assignTarget) {
                    return;
                  }
                  assignMutation.mutate({
                    userId: assignTarget.id,
                    payload: values,
                  });
                });
              }}
            >
              {t('adminUsers.assignSave')}
            </Button>
          </Space>
        }
      >
        <Form form={assignForm} layout="vertical">
          <Form.Item
            name="department_id"
            label={t('adminUsers.department')}
            rules={[{ required: true, message: t('adminUsers.departmentRequired') }]}
          >
            <Select
              showSearch
              optionFilterProp="label"
              options={deptSelectOptions}
            />
          </Form.Item>
          <Form.Item
            name="role"
            label={t('adminUsers.deptRoleLabel')}
            rules={[{ required: true }]}
          >
            <Select
              options={[
                { value: 'chuyenvien', label: t('adminUsers.deptRole.chuyenvien') },
                { value: 'lanhdao', label: t('adminUsers.deptRole.lanhdao') },
              ]}
            />
          </Form.Item>
        </Form>
      </Drawer>

      <Modal
        title={t('adminUsers.deactivateTitle')}
        open={Boolean(deactivateTarget)}
        onCancel={() => setDeactivateTarget(null)}
        onOk={confirmDeactivate}
        okText={t('adminUsers.deactivateConfirm')}
        okButtonProps={{ danger: true, loading: updateMutation.isPending }}
      >
        <Typography.Paragraph>
          {t('adminUsers.deactivateMessage', {
            name: deactivateTarget?.display_name,
          })}
        </Typography.Paragraph>
      </Modal>

      <Modal
        title={t('adminUsers.setPasswordTitle', {
          name: passwordTarget?.display_name,
        })}
        open={Boolean(passwordTarget)}
        onCancel={() => {
          setPasswordTarget(null);
          passwordForm.resetFields();
        }}
        onOk={() => {
          void passwordForm.validateFields().then((values) => {
            if (!passwordTarget) {
              return;
            }
            passwordMutation.mutate({
              userId: passwordTarget.id,
              password: values.password,
            });
          });
        }}
        okText={t('adminUsers.setPasswordSave')}
        okButtonProps={{ loading: passwordMutation.isPending }}
        destroyOnClose
      >
        <Typography.Paragraph type="secondary">
          {t('adminUsers.setPasswordHint')}
        </Typography.Paragraph>
        <Form form={passwordForm} layout="vertical">
          <Form.Item
            name="password"
            label={t('adminUsers.newPassword')}
            rules={[
              { required: true, message: t('adminUsers.passwordRequired') },
              { min: 8, message: t('adminUsers.passwordMin') },
            ]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm_password"
            label={t('adminUsers.confirmPassword')}
            dependencies={['password']}
            rules={[
              { required: true, message: t('adminUsers.confirmPasswordRequired') },
              ({ getFieldValue }) => ({
                validator(_, value: string) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error(t('adminUsers.passwordMismatch')));
                },
              }),
            ]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}

import { endpoints } from "./endpoints";
import type { RbacDelegation, RbacPermission, RbacRole, RbacUser } from "../types/rbac";
import { deleteData, getData, postData } from "./http";

export async function fetchRbacRoles() {
  return getData<RbacRole[]>(endpoints.admin.rbacRoles);
}

export async function fetchRbacPermissions() {
  return getData<RbacPermission[]>(endpoints.admin.rbacPermissions);
}

export async function fetchRbacUsers() {
  return getData<RbacUser[]>(endpoints.admin.rbacUsers);
}

export async function fetchRbacDelegations() {
  return getData<RbacDelegation[]>(endpoints.admin.rbacDelegations);
}

export async function assignPermissionToRole(roleId: number, permissionId: number) {
  return postData<RbacRole>(endpoints.admin.assignRolePermission(roleId, permissionId));
}

export async function unassignPermissionFromRole(roleId: number, permissionId: number) {
  return deleteData<RbacRole>(endpoints.admin.assignRolePermission(roleId, permissionId));
}

export async function assignRoleToUser(userId: number, roleId: number) {
  return postData<RbacUser>(endpoints.admin.assignUserRole(userId, roleId));
}

export async function unassignRoleFromUser(userId: number, roleId: number) {
  return deleteData<RbacUser>(endpoints.admin.assignUserRole(userId, roleId));
}

export async function createDelegation(payload: {
  grantor_user_id: number;
  grantee_user_id: number;
  permission_name: string;
  expires_at?: string | null;
}) {
  return postData<RbacDelegation, typeof payload>(endpoints.admin.rbacDelegations, payload);
}

export async function revokeDelegation(delegationId: number) {
  return deleteData<RbacDelegation>(endpoints.admin.revokeDelegation(delegationId));
}

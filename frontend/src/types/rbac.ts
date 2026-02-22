export type RbacRole = {
  id: number;
  name: string;
  permissions: string[];
};

export type RbacPermission = {
  id: number;
  name: string;
};

export type RbacUser = {
  id: number;
  email: string;
  roles: string[];
};

export type RbacDelegation = {
  id: number;
  grantor_user_id: number;
  grantor_email: string | null;
  grantee_user_id: number;
  grantee_email: string | null;
  permission_name: string;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string;
};

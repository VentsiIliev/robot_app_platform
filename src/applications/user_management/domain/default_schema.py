from src.applications.user_management.domain.user_schema import UserSchema, FieldDescriptor

# Default schema matching the original User model — reuse or replace per robot vision_service
DEFAULT_USER_SCHEMA = UserSchema(
    id_key="id",
    fields=[
        FieldDescriptor(key="id",        label="ID",         widget="int",      required=True,  read_only_on_edit=True),
        FieldDescriptor(key="firstName", label="First Name", widget="text",     required=True),
        FieldDescriptor(key="lastName",  label="Last Name",  widget="text",     required=True),
        FieldDescriptor(key="password",  label="Password",   widget="password", required=True,  mask_in_table=True),
        FieldDescriptor(key="role",      label="Role",       widget="combo",    required=True,
                        options=["Admin", "Operator", "Viewer"]),
        FieldDescriptor(key="email",     label="Email",      widget="email",    required=False),
    ],
)


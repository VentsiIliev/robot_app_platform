from core.application.ApplicationContext import get_users_storage_path
from frontend.core.shared.base_widgets.AppWidget import AppWidget

import os

application_users_storage = get_users_storage_path()
if application_users_storage is not None:
    csv_file_path = os.path.join(application_users_storage, "users.csv")
    print(f"UserManagementAppWidget: Using CSV APPLICATION FILE PATH: {csv_file_path}")
else:
    # Go up four levels to reach the project root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"UserManagementAppWidget: Base directory determined as: {base_dir}")
    project_root = os.path.abspath(os.path.join(base_dir, "..", "..", "..", "..", ".."))
    print(f"UserManagementAppWidget: Project root determined as: {project_root}")
    csv_file_path = os.path.join(project_root, "shared", "shared", "user", "users.csv")
    print(f"[WARNING] UserManagementAppWidget: Using CSV DEFAULT FILE PATH: {csv_file_path}")

class UserManagementAppWidget(AppWidget):
    """Specialized widget for User Management application"""

    def __init__(self, parent=None):
        super().__init__("User Management", parent)

    def setup_ui(self):
        """Set up the user management specific UI"""
        super().setup_ui()  # Get the basic layout with back button

        # Replace the content with actual UserManagementWidget if available
        try:
            from plugins.core.user_management.ui.UserDashboard import UserManagementWidget
            # Remove the placeholder content
            content_widget = UserManagementWidget(csv_file_path=csv_file_path)

            # Replace the last widget in the layout (the placeholder) with the real widget
            layout = self.layout()
            old_content = layout.itemAt(layout.count() - 1).widget()
            layout.removeWidget(old_content)
            old_content.deleteLater()

            layout.addWidget(content_widget)
        except ImportError:
            import traceback
            traceback.print_exc()
            # Keep the placeholder if the UserManagementWidget is not available
            print("UserManagementWidget not available, using placeholder")

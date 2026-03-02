"""
Glue Change Wizard - uses generic wizard framework.
"""

from pathlib import Path
from typing import Optional
import sys

from PyQt6.QtWidgets import QApplication

try:
    from dashboard.ui.wizards import (
        WizardStepConfig,
        GenericWizardStep,
        SelectionStep,
        SummaryStep,
        ConfigurableWizard
    )
except ImportError:
    from pl_gui.utils.utils_widgets.wizards import (
        WizardStepConfig,
        GenericWizardStep,
        SelectionStep,
        SummaryStep,
        ConfigurableWizard
    )


def create_glue_change_wizard(glue_type_names: Optional[list] = None):
    """
    Factory function to create a glue change wizard.

    Args:
        glue_type_names: List of available glue type names

    Returns:
        ConfigurableWizard instance
    """
    # Define wizard steps
    # Get resource paths
    resources_dir = Path(__file__).parents[2] / "dashboard" / "resources"
    icon_path = str(resources_dir / "logo.ico") if (resources_dir / "logo.ico").exists() else None
    logo_path = icon_path  # Use same icon as logo
    steps = [
        # Welcome
        GenericWizardStep(WizardStepConfig(
            title="Glue Change Guide",
            subtitle="Welcome to the Glue Change Wizard",
            description="This wizard will guide you through the process of changing the glue container. Click Next to continue.",
            image_path = logo_path
        )),

        # Step 1: Open Drawer
        GenericWizardStep(WizardStepConfig(
            title="Open Drawer",
            subtitle="Open the glue container drawer",
            description="Locate and carefully open the drawer containing the glue container.",
            step_number=1,
            image_path=logo_path
        )),

        # Step 2: Disconnect Hose
        GenericWizardStep(WizardStepConfig(
            title="Disconnect Hose",
            subtitle="Disconnect the hose from the glue container",
            description="Carefully disconnect the hose from the current glue container.",
            step_number=2,
            image_path=logo_path
        )),

        # Step 3: Place New Container
        GenericWizardStep(WizardStepConfig(
            title="Place New Glue Container",
            subtitle="Place the new glue container in the drawer",
            description="Remove the old glue container and place the new one in its position.",
            step_number=3,
            image_path=logo_path
        )),

        # Step 4: Connect Hose
        GenericWizardStep(WizardStepConfig(
            title="Connect Hose",
            subtitle="Connect the hose to the new container",
            description="Securely connect the hose to the new glue container.",
            step_number=4,
            image_path=logo_path
        )),

        # Step 5: Close Drawer
        GenericWizardStep(WizardStepConfig(
            title="Close Drawer",
            subtitle="Close the glue container drawer",
            description="Carefully close the drawer. Make sure everything is secured properly.",
            step_number=5,
            image_path=logo_path
        )),

        # Step 6: Select Glue Type
        SelectionStep(
            config=WizardStepConfig(
                title="Select Glue Type",
                subtitle="Select the type of the new glue",
                description="Choose the type of glue you have installed from the options below.",
                step_number=6,
                image_path=logo_path
            ),
            options=glue_type_names or [],
            selection_label="Select Glue Type:",
            empty_message="No glue types configured!",
            empty_instructions="Please configure glue types in:\n1. Glue Cell Settings\n2. Or register custom glue types"
        ),

        # Summary
        SummaryStep(
            config=WizardStepConfig(
                title="Summary",
                subtitle="Glue change completed",
                description="Review the completed steps and the selected glue type.",
                image_path=logo_path
            ),
            summary_generator=lambda wizard: generate_glue_change_summary(wizard)
        )
    ]



    # Create wizard
    wizard = ConfigurableWizard(
        title="Glue Change Wizard",
        pages=steps,
        icon_path=icon_path,
        logo_path=logo_path,
        min_width=600,
        min_height=500,
        on_finish_callback=on_glue_change_finished
    )

    return wizard


def generate_glue_change_summary(wizard: ConfigurableWizard) -> str:
    """Generate HTML summary for glue change wizard."""
    # Get the selection step (page index 6)
    selection_page = wizard.page(6)
    glue_type = selection_page.get_selected_option() if hasattr(selection_page, 'get_selected_option') else "Unknown"

    return f"""
<b>Glue Change Steps Completed:</b><br>
✓ Drawer opened<br>
✓ Hose disconnected from old container<br>
✓ New glue container placed<br>
✓ Hose connected to new container<br>
✓ Drawer closed<br><br>
<b>Selected Glue Type:</b> {glue_type}
    """


def on_glue_change_finished(wizard: ConfigurableWizard):
    """Callback when glue change wizard finishes."""
    selection_page = wizard.page(6)
    selected_type = selection_page.get_selected_option() if hasattr(selection_page, 'get_selected_option') else None
    print(f"Glue change completed! Selected: {selected_type}")



def main():
    """Standalone test for glue change wizard."""
    app = QApplication(sys.argv)
    wizard = create_glue_change_wizard(["PUR Hotmelt", "EVA Adhesive", "Silicone"])
    wizard.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

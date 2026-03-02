"""Contour Editor Application Widget"""
from contour_editor import SettingsGroup, BezierSegmentManager, ContourEditorData
from contour_editor.persistence.model.SettingsConfig import SettingsConfig
from robot_systems.glue.applications.workpiece_editor.workpiece_editor.config import SegmentSettingsProvider, WorkpieceFormFactory

from src.robot_systems.glue.settings.glue import GlueSettingKey

from robot_systems.glue.applications.workpiece_editor.workpiece_editor.config import GlueSettingsProvider

from robot_systems.glue.applications.workpiece_editor.workpiece_editor.config.virtual_keyboard_widget_factory import \
    VirtualKeyboardWidgetFactory

from robot_systems.glue.applications.workpiece_editor.workpiece_editor import WorkpieceEditorBuilder, WorkpieceAdapter


from pl_gui.shell.base_app_widget.AppWidget import AppWidget



class ContourEditorAppWidget(AppWidget):
    """Specialized widget for User Management application"""

    def __init__(self, parent=None,controller=None):
        self.controller = controller
        self.parent = parent
        self.content_widget = None
        super().__init__("Contour Editor", parent)

    def setup_ui(self):
        """Set up the user management specific UI"""
        super().setup_ui()  # Get the basic layout with the back button

        # Replace the content with the actual UserManagementWidget if available
        try:

            print("Creating contour editor widget using builder...")
            self.content_widget = self._build_workpiece_editor()
            print(f"✅ Contour editor widget created: {type(self.content_widget)}")

            # Inject controller into content_widget for backward compatibility
            self.content_widget.controller = self.controller

            # Connect signals for nested editor components (fetch glue types, etc.)
            self._connect_editor_signals()

            print("✅ Contour editor callbacks configured via builder")

            # Replace the last widget in the layout (the placeholder) with the real widget
            layout = self.layout()
            print(f"🔍 Current layout items count: {layout.count()}")
            
            if layout.count() > 0:
                old_content = layout.itemAt(layout.count() - 1).widget()
                print(f"🗑️ Removing old placeholder: {type(old_content)}")
                layout.removeWidget(old_content)
                old_content.deleteLater()
            
            layout.addWidget(self.content_widget)

            print(f"✅ Contour editor widget added to layout. Total items: {layout.count()}")

        except Exception as e:
            print(f"❌ Failed to create contour editor: {e}")
            import traceback
            traceback.print_exc()

    def _connect_editor_signals(self):
        """Connect signals from editor components"""
        try:
            if hasattr(self.content_widget, 'settings_widget'):
                settings_widget = self.content_widget.settings_widget

                # Connect glue type fetch callback to combo widget if it exists
                if hasattr(settings_widget, 'combo_widget'):
                    print("Connecting glue type fetch callback to combo widget...")
                    combo_widget = settings_widget.combo_widget
                    if hasattr(combo_widget, 'set_fetch_options_callback'):
                        combo_widget.set_fetch_options_callback(self._fetch_glue_types)
                        print("✓ Glue type fetch callback connected")
                    else:
                        print("⚠ combo_widget has no set_fetch_options_callback method")
                else:
                    print("⚠ settings_widget has no combo_widget attribute")
            else:
                print("⚠ content_widget has no settings_widget attribute")
        except Exception as e:
            print(f"⚠ Error connecting editor signals: {e}")
            import traceback
            traceback.print_exc()

    def _fetch_glue_types(self):
        """Fetch available glue types"""
        try:
            from modules.shared.tools.glue_monitor_system.core.cell_manager import GlueCellsManagerSingleton
            cells_manager = GlueCellsManagerSingleton.get_instance()
            if cells_manager.cells:
                glue_types = [cell.glueType for cell in cells_manager.cells if cell.glueType]
                print(f"Fetched glue types: {glue_types}")
                return glue_types if glue_types else ["Default Type"]
            return ["Default Type"]
        except Exception as e:
            print(f"WARNING: Could not fetch glue types: {e}")
            return ["Default Type"]

    def on_update_camera_feed_requested(self):
        image = self.controller.handle(camera_endpoints.UPDATE_CAMERA_FEED)
        if image is None:
            # print("No image received for camera feed update")
            return
        self.content_widget.set_image(image)
        # print(f"Updated camera feed in Contour Editor")

    def handle_save_workpiece_callback(self, workpiece_data):
        """
        Callback for when a user clicks the 'Save Workpiece' button.
        This is passed to the builder and called from the editor widget.
        """
        from plugins.core.contour_editor.workpiece_editor.handlers.SaveWorkpieceHandler import SaveWorkpieceHandler

        print(f"[ContourEditorAppWidget] Save workpiece callback triggered with data: {list(workpiece_data.keys())}")

        form_data = workpiece_data.get('form_data', {})
        editor_data = workpiece_data.get('editor_data')

        print(f"Save_workpiece: form data: {form_data}")

        # Use SaveWorkpieceHandler to transform, validate and save
        # It will use WorkpieceAdapter internally to transform editor_data
        try:
            success, message = SaveWorkpieceHandler.save_workpiece(
                workpiece_manager=self.content_widget.contourEditor.workpiece_manager,
                form_data=form_data,  # Pass raw form_data
                editor_data=editor_data,  # Pass raw editor_data
                controller=self.controller
            )

            if success:
                print(f"✅ Workpiece saved successfully: {message}")
            else:
                print(f"❌ Failed to save workpiece: {message}")

            return success, message
        except Exception as e:
            error_msg = f"Error saving workpiece: {str(e)}"
            print(f"[ContourEditorAppWidget] {error_msg}")
            import traceback
            traceback.print_exc()
            return False, error_msg


    def handle_capture_callback(self):
        """
        Callback for when user clicks 'Capture' button.
        This is passed to the builder and called from the editor widget.
        """
        print("[ContourEditorAppWidget] Capture callback triggered")

        try:
            # Call the controller to capture image
            result = self.controller.capture_frame()
            print(f"[ContourEditorAppWidget] Controller capture result: {result}")

            if result and hasattr(result, 'success') and result.success:
                # Return the image data
                return result.data.get('image')
            else:
                print(f"[ContourEditorAppWidget] Capture failed: {result}")
                return None
        except Exception as e:
            print(f"[ContourEditorAppWidget] Error during capture: {e}")
            import traceback
            traceback.print_exc()
            return None

    def handle_get_contours_callback(self):
        """
        Callback to get detected contours from the controller.
        This is passed to the builder and called from the editor widget.
        """
        print("[ContourEditorAppWidget] Get contours callback triggered")

        try:
            result = self.controller.get_detected_contours()
            print(f"[ContourEditorAppWidget] Controller get contours result: {result}")

            if result and hasattr(result, 'success') and result.success:
                contours = result.data.get('contours', [])
                print(f"[ContourEditorAppWidget] Retrieved {len(contours)} contours")
                return contours
            else:
                print(f"[ContourEditorAppWidget] Get contours failed: {result}")
                return []
        except Exception as e:
            print(f"[ContourEditorAppWidget] Error getting contours: {e}")
            import traceback
            traceback.print_exc()
            return []

    def handle_detect_contours_callback(self, image):
        """
        Callback for when user needs to detect contours from an image.
        This is passed to the builder and called from the editor widget.
        """
        print(f"[ContourEditorAppWidget] Detect contours callback triggered with image: {type(image)}")

        try:
            result = self.controller.detect_contours(image)
            print(f"[ContourEditorAppWidget] Controller detect contours result: {result}")

            if result and hasattr(result, 'success') and result.success:
                contours = result.data.get('contours', [])
                print(f"[ContourEditorAppWidget] Detected {len(contours)} contours")
                return contours
            else:
                print(f"[ContourEditorAppWidget] Detect contours failed: {result}")
                return []
        except Exception as e:
            print(f"[ContourEditorAppWidget] Error detecting contours: {e}")
            import traceback
            traceback.print_exc()
            return []

    def handle_execute_callback(self, workpiece_data):
        """
        Callback for when user clicks 'Execute' button.
        This executes the workpiece immediately (test/debug mode).
        """
        print(f"[ContourEditorAppWidget] Execute callback triggered with data: {list(workpiece_data.keys())}")

        # Import required field providers and enums

        import uuid

        # Build a minimal form_data with required fields
        # These would normally come from a form, but for "execute" we use defaults
        form_data = workpiece_data.get('form_data')
        if not form_data:
            form_data = {
                # Required GlueWorkpiece fields with valid enum values
                GlueWorkpieceField.WORKPIECE_ID.value: str(uuid.uuid4()),
                GlueWorkpieceField.NAME.value: "Test Workpiece",
                GlueWorkpieceField.DESCRIPTION.value: "Test workpiece created via contour editor",
                GlueWorkpieceField.TOOL_ID.value: ToolID.Tool1,
                GlueWorkpieceField.GRIPPER_ID.value: Gripper.SINGLE,
                GlueWorkpieceField.PROGRAM.value: Program.TRACE,
                GlueWorkpieceField.MATERIAL.value: "Default Material",
                GlueWorkpieceField.OFFSET.value: 0,
                GlueWorkpieceField.HEIGHT.value: 4,
                GlueWorkpieceField.CONTOUR_AREA.value: 0,
                GlueWorkpieceField.GLUE_QTY.value: 0,
                GlueWorkpieceField.SPRAY_WIDTH.value: 10,
                GlueWorkpieceField.PICKUP_POINT.value: None,
                GlueWorkpieceField.NOZZLES.value: [],
                GlueWorkpieceField.GLUE_TYPE.value: "Type A",
            }
            print(f"[ContourEditorAppWidget] Using default form data with ToolID={ToolID.Tool1.name}, Gripper={Gripper.SINGLE.name}, Program={Program.TRACE.name}, GlueType=Type A")

        # Transform editor_data to workpiece format using WorkpieceAdapter
        if 'editor_data' in workpiece_data:


            editor_data = workpiece_data['editor_data']
            if isinstance(editor_data, ContourEditorData):
                # Transform editor data to workpiece format (includes contour, sprayPattern, and all settings)
                transformed_data = WorkpieceAdapter.to_workpiece_data(editor_data)
                print(f"[ContourEditorAppWidget] Transformed editor data, keys: {list(transformed_data.keys())}")

                # Merge: transformed_data first (has contour/sprayPattern), then form_data overrides (has enums)
                complete_data = {**transformed_data, **form_data}
            else:
                print(f"[ContourEditorAppWidget] Warning: editor_data is not ContourEditorData, type: {type(editor_data)}")
                complete_data = {**form_data, **workpiece_data}
        else:
            # No editor_data, just merge as-is
            print(f"[ContourEditorAppWidget] Warning: No editor_data found in workpiece_data")
            complete_data = {**form_data, **workpiece_data}

        print(f"[ContourEditorAppWidget] Complete data for GlueWorkpiece: {list(complete_data.keys())}")

        workpiece = GlueWorkpiece.from_dict(complete_data)
        print(f"[ContourEditorAppWidget] Executing workpiece via controller: {workpiece}")
        try:
            self.controller.handleExecuteFromGallery(workpiece)
        except Exception as e:
            print(f"[ContourEditorAppWidget] Error executing workpiece: {e}")
            import traceback
            traceback.print_exc()


    def _build_workpiece_editor(self):
        """
        Build a workpiece editor configured for glue dispensing application.
        Uses the widget's callbacks for save, capture, and execute operations.
        """
        print("Building workpiece editor with glue dispensing configuration...")

        # Import builder components


        # Get available glue types
        def _get_available_glue_types():
            try:
                cells_manager = GlueCellsManagerSingleton.get_instance()
                if cells_manager.cells:
                    glue_types = [cell.glueType for cell in cells_manager.cells if cell.glueType]
                    print(f"Available glue types: {glue_types}")
                    return glue_types if glue_types else ["Default Type"]
                return ["Default Type"]
            except Exception as e:
                print(f"WARNING: Could not load glue types: {e}")
                return ["Default Type"]

        # Use SegmentSettingsProvider to get default settings
        settings_provider_instance = SegmentSettingsProvider(material_types=_get_available_glue_types())
        default_settings = settings_provider_instance.get_default_values()

        # Create settings configuration for glue dispensing
        config = SettingsConfig(
            default_settings=default_settings,
            groups=[
                SettingsGroup("General Settings", [
                    GlueSettingKey.SPRAY_WIDTH.value,
                    GlueSettingKey.SPRAYING_HEIGHT.value,
                    GlueSettingKey.GLUE_TYPE.value,
                ]),
                SettingsGroup("Forward Motion Settings", [
                    GlueSettingKey.FORWARD_RAMP_STEPS.value,
                    GlueSettingKey.INITIAL_RAMP_SPEED.value,
                    GlueSettingKey.INITIAL_RAMP_SPEED_DURATION.value,
                    GlueSettingKey.MOTOR_SPEED.value,
                ]),
                SettingsGroup("Reverse Motion Settings", [
                    GlueSettingKey.REVERSE_DURATION.value,
                    GlueSettingKey.SPEED_REVERSE.value,
                    GlueSettingKey.REVERSE_RAMP_STEPS.value,
                ]),
                SettingsGroup("Robot Settings", [
                    RobotSettingKey.VELOCITY.value,
                    RobotSettingKey.ACCELERATION.value,
                    GlueSettingKey.RZ_ANGLE.value,
                    GlueSettingKey.ADAPTIVE_SPACING_MM.value,
                    GlueSettingKey.SPLINE_DENSITY_MULTIPLIER.value,
                    GlueSettingKey.SMOOTHING_LAMBDA.value,
                ]),
                SettingsGroup("Generator Settings", [
                    GlueSettingKey.TIME_BETWEEN_GENERATOR_AND_GLUE.value,
                    GlueSettingKey.GENERATOR_TIMEOUT.value,
                ]),
                SettingsGroup("Reach Threshold Settings (mm)", [
                    GlueSettingKey.REACH_START_THRESHOLD.value,
                    GlueSettingKey.REACH_END_THRESHOLD.value,
                ]),
                SettingsGroup("Pump speed adjustment", [
                    GlueSettingKey.GLUE_SPEED_COEFFICIENT.value,
                    GlueSettingKey.GLUE_ACCELERATION_COEFFICIENT.value,
                ]),
            ],
            combo_field_key=GlueSettingKey.GLUE_TYPE.value,
        )

        # Create custom settings provider for glue dispensing (using same default_settings)
        provider = GlueSettingsProvider(
            default_settings=default_settings,
            material_types=_get_available_glue_types(),
            material_type_key=GlueSettingKey.GLUE_TYPE.value
        )

        # Create workpiece form factory with glue types
        print("Creating workpiece form factory...")
        form_factory = WorkpieceFormFactory(glue_types=_get_available_glue_types())

        # Create custom widget factory for virtual keyboard support
        print("Creating virtual keyboard widget factory...")
        keyboard_factory = VirtualKeyboardWidgetFactory()

        # Build the editor
        print("Building editor with all configurations...")
        builder = WorkpieceEditorBuilder()
        editor_widget = (
            builder
            .with_segment_manager(BezierSegmentManager)
            .with_settings(config, provider)
            .with_form(form_factory)
            .with_widgets(keyboard_factory)
            .on_save(self.handle_save_workpiece_callback)
            .on_capture(self.handle_get_contours_callback)
            .on_execute(self.handle_execute_callback)
            .on_update_camera_feed(self.on_update_camera_feed_requested)
            .build()
        )
        print(f"✅ Workpiece editor built successfully: {type(editor_widget)}")
        return editor_widget

    def set_create_workpiece_for_on_submit_callback(self, callback):
        """Set the callback for when the create workpiece button is clicked"""
        try:
            print("Setting create workpiece callback")
            self.content_widget.set_create_workpiece_for_on_submit_callback(callback)
        except AttributeError:
            print("Contour Editor widget does not support set_create_workpiece_for_on_submit_callback method")

    def load_workpiece(self,workpiece):
        self.content_widget.contourEditor.load_workpiece(workpiece)

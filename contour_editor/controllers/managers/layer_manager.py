class LayerManager:
    def __init__(self, editor):
        self.editor = editor

    def set_layer_visibility(self, layer_name, visible):
        """Set visibility of a specific layer"""
        layer = self.get_layer_by_name(layer_name)
        if layer is None:
            print(f"Invalid layer: {layer_name}")
            return

        layer.visible = visible

        # Update all segments in this layer
        for idx, segment in enumerate(self.editor.manager.get_segments()):
            if hasattr(segment, 'layer') and segment.layer.name == layer.name:
                self.editor.manager.set_segment_visibility(idx, visible)

        self.editor.update()  # Redraw after visibility change

    def set_layer_locked(self, layer_name, locked):
        """Set lock state of a specific layer"""
        self.editor.manager.set_layer_locked(layer_name, locked)
        print(f"Layer lock state updated: {layer_name}, locked={locked}")

    def get_layer_by_name(self, layer_name):
        """Get layer object by name"""
        if hasattr(self.editor.manager, "_layer_for_name"):
            return self.editor.manager._layer_for_name(layer_name)
        return None

    def get_all_layers(self):
        """Get all available layers"""
        layers = []
        if hasattr(self.editor.manager, 'get_available_layer_names'):
            for layer_name in self.editor.manager.get_available_layer_names():
                layer = self.get_layer_by_name(layer_name)
                if layer is not None:
                    layers.append((layer_name, layer))
        return layers

    def get_layer_info(self, layer_name):
        """Get information about a specific layer"""
        layer = self.get_layer_by_name(layer_name)
        if layer is None:
            return None

        # Count segments in this layer
        segment_count = 0
        for segment in self.editor.manager.get_segments():
            if hasattr(segment, 'layer') and segment.layer.name == layer.name:
                segment_count += 1

        return {
            "name": layer_name,
            "visible": layer.visible if hasattr(layer, 'visible') else True,
            "locked": layer.locked if hasattr(layer, 'locked') else False,
            "segment_count": segment_count
        }

    def toggle_layer_visibility(self, layer_name):
        """Toggle visibility of a layer"""
        layer = self.get_layer_by_name(layer_name)
        if layer is not None:
            current_visibility = getattr(layer, 'visible', True)
            self.set_layer_visibility(layer_name, not current_visibility)
            return not current_visibility
        return None

    def toggle_layer_lock(self, layer_name):
        """Toggle lock state of a layer"""
        layer = self.get_layer_by_name(layer_name)
        if layer is not None:
            current_lock = getattr(layer, 'locked', False)
            self.set_layer_locked(layer_name, not current_lock)
            return not current_lock
        return None

    def get_visible_layers(self):
        """Get list of currently visible layers"""
        visible_layers = []
        for layer_name, layer in self.get_all_layers():
            if getattr(layer, 'visible', True):
                visible_layers.append(layer_name)
        return visible_layers

    def get_locked_layers(self):
        """Get list of currently locked layers"""
        locked_layers = []
        for layer_name, layer in self.get_all_layers():
            if getattr(layer, 'locked', False):
                locked_layers.append(layer_name)
        return locked_layers

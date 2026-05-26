class ListItemData:
    """
    Data class for QListWidgetItem user data.
    Represents different types of items in the point manager list.
    """
    def __init__(self, item_type, layer_name=None, seg_index=None, point_index=None, point_type=None):
        self.item_type = item_type  # 'layer', 'segment', 'point'
        self.layer_name = layer_name
        self.seg_index = seg_index
        self.point_index = point_index
        self.point_type = point_type  # 'anchor' or 'control'
    def __repr__(self):
        if self.item_type == 'layer':
            return f"ListItemData(layer={self.layer_name})"
        elif self.item_type == 'segment':
            return f"ListItemData(segment={self.seg_index}, layer={self.layer_name})"
        elif self.item_type == 'point':
            return f"ListItemData(point={self.point_type}[{self.point_index}], segment={self.seg_index})"
        return f"ListItemData(type={self.item_type})"

"""Protobuf bindings derived from proto/inventory.proto (descriptor-based)."""
from google.protobuf import descriptor_pool
from google.protobuf.internal import builder
DESCRIPTOR = descriptor_pool.Default().AddSerializedFile(b'\n\x0finventory.proto\x12\tinventory",\n\x04Item\x12\x12\n\nproduct_id\x18\x01 \x01(\x05\x12\x10\n\x08quantity\x18\x02 \x01(\x05".\n\x0cItemsRequest\x12\x1e\n\x05items\x18\x01 \x03(\x0b2\x0f.inventory.Item""\n\rCheckResponse\x12\x11\n\tavailable\x18\x01 \x01(\x08"3\n\x0fReserveResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t2\xdd\x01\n\x10InventoryService\x12?\n\nCheckStock\x12\x17.inventory.ItemsRequest\x1a\x18.inventory.CheckResponse\x12C\n\x0cReserveStock\x12\x17.inventory.ItemsRequest\x1a\x1a.inventory.ReserveResponse\x12C\n\x0cReleaseStock\x12\x17.inventory.ItemsRequest\x1a\x1a.inventory.ReserveResponseb\x06proto3')
builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, __name__, globals())

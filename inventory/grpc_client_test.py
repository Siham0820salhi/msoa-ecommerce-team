import grpc

import inventory_pb2
import inventory_pb2_grpc

channel = grpc.insecure_channel("localhost:50051")
stub = inventory_pb2_grpc.InventoryServiceStub(channel)


def items(*pairs):
    return inventory_pb2.ItemsRequest(
        items=[inventory_pb2.Item(product_id=p, quantity=q) for p, q in pairs]
    )


print("1. CheckStock produit 1 x2   :", stub.CheckStock(items((1, 2))).available)
print("2. CheckStock produit 1 x999 :", stub.CheckStock(items((1, 999))).available)
print("3. ReserveStock produit 1 x2 :", stub.ReserveStock(items((1, 2))).success)

try:
    stub.ReserveStock(items((1, 2), (5, 999)))
except grpc.RpcError as e:
    print("4. Reserve multi (echec)     :", e.code().name, "|", e.details())

try:
    stub.ReserveStock(items((999, 1)))
except grpc.RpcError as e:
    print("5. Reserve produit inconnu   :", e.code().name, "|", e.details())

print("6. ReleaseStock produit 1 x2 :", stub.ReleaseStock(items((1, 2))).success)
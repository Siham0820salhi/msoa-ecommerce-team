"""Serveur gRPC d'Inventory (port 50051).
Réutilise les fonctions REST de main.py : même logique atomique."""
from concurrent import futures

import grpc
from pydantic import ValidationError

import inventory_pb2
import inventory_pb2_grpc
from main import ApiError, Item, ItemsRequest, check, release, reserve

PORT = 50051

GRPC_CODES = {
    400: grpc.StatusCode.INVALID_ARGUMENT,
    404: grpc.StatusCode.NOT_FOUND,
    409: grpc.StatusCode.FAILED_PRECONDITION,
}


def to_request(request) -> ItemsRequest:
    return ItemsRequest(
        items=[Item(productId=i.product_id, quantity=i.quantity) for i in request.items]
    )


class InventoryServicer(inventory_pb2_grpc.InventoryServiceServicer):
    def CheckStock(self, request, context):
        try:
            result = check(to_request(request))
        except ValidationError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "productId and quantity > 0 required")
        return inventory_pb2.CheckResponse(available=result["available"])

    def ReserveStock(self, request, context):
        try:
            reserve(to_request(request))
        except ValidationError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "productId and quantity > 0 required")
        except ApiError as e:
            context.abort(GRPC_CODES.get(e.status, grpc.StatusCode.INTERNAL), e.message)
        return inventory_pb2.ReserveResponse(success=True, message="reserved")

    def ReleaseStock(self, request, context):
        try:
            release(to_request(request))
        except ValidationError:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "productId and quantity > 0 required")
        except ApiError as e:
            context.abort(GRPC_CODES.get(e.status, grpc.StatusCode.INTERNAL), e.message)
        return inventory_pb2.ReserveResponse(success=True, message="released")


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_InventoryServiceServicer_to_server(InventoryServicer(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    server.start()
    print(f"Inventory gRPC server listening on port {PORT}")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
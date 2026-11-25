"""gRPC client for the shared Inventory contract; no automatic mutation retries."""
import grpc
from app import config
from app.errors import ApiError
from app.clients import inventory_pb2 as pb

_CODES = {grpc.StatusCode.INVALID_ARGUMENT: 400, grpc.StatusCode.NOT_FOUND: 404,
          grpc.StatusCode.FAILED_PRECONDITION: 409, grpc.StatusCode.UNAVAILABLE: 503,
          grpc.StatusCode.DEADLINE_EXCEEDED: 503}


def _invoke(method, items):
    try:
        request = pb.ItemsRequest(items=[pb.Item(product_id=i['productId'], quantity=i['quantity']) for i in items])
    except (ValueError, TypeError, OverflowError) as exc:
        raise ApiError(400, 'Invalid inventory items') from exc
    try:
        with grpc.insecure_channel(config.INVENTORY_GRPC_TARGET) as channel:
            rpc = channel.unary_unary('/inventory.InventoryService/' + method,
                request_serializer=pb.ItemsRequest.SerializeToString,
                response_deserializer=pb.ReserveResponse.FromString)
            response = rpc(request, timeout=config.GRPC_TIMEOUT)
    except grpc.RpcError as exc:
        code = _CODES.get(exc.code(), 502)
        message = exc.details() or 'Inventory request failed'
        if code == 503:
            message = 'Inventory service unavailable: ' + message
        raise ApiError(code, message) from exc
    if not response.success:
        raise ApiError(409 if method == 'ReserveStock' else 502, response.message or 'Inventory operation refused')


def reserve(items):
    _invoke('ReserveStock', items)


def release(items):
    _invoke('ReleaseStock', items)

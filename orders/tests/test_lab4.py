from concurrent.futures import ThreadPoolExecutor
import grpc
import pytest
from app import config
from app.clients import inventory_client, inventory_pb2 as pb, events


@pytest.fixture
def grpc_inventory(monkeypatch, services):
    stock = services.inventory
    def handler(method):
        def run(request, context):
            from app.errors import ApiError
            try:
                method([{'productId': i.product_id, 'quantity': i.quantity} for i in request.items])
            except ApiError as exc:
                context.abort({409: grpc.StatusCode.FAILED_PRECONDITION, 404: grpc.StatusCode.NOT_FOUND, 503: grpc.StatusCode.UNAVAILABLE, 502: grpc.StatusCode.INTERNAL}[exc.status_code], exc.message)
            return pb.ReserveResponse(success=True)
        return grpc.unary_unary_rpc_method_handler(run, request_deserializer=pb.ItemsRequest.FromString, response_serializer=pb.ReserveResponse.SerializeToString)
    server = grpc.server(ThreadPoolExecutor(max_workers=2))
    server.add_generic_rpc_handlers((grpc.method_handlers_generic_handler('inventory.InventoryService', {'ReserveStock': handler(stock.reserve), 'ReleaseStock': handler(stock.release)}),))
    port = server.add_insecure_port('127.0.0.1:0')
    server.start()
    monkeypatch.setattr(config, 'INVENTORY_GRPC_TARGET', f'127.0.0.1:{port}')
    monkeypatch.setattr(inventory_client, 'reserve', lambda items: inventory_client._invoke('ReserveStock', items))
    monkeypatch.setattr(inventory_client, 'release', lambda items: inventory_client._invoke('ReleaseStock', items))
    yield server
    server.stop(0).wait()


def test_grpc_lifecycle(grpc_inventory, services, make_order, client, user1):
    result = make_order()
    assert result.status_code == 201
    assert services.inventory.stock[1] == 8
    oid = result.json()['id']
    assert make_order(items=[{'productId': 1, 'quantity': 99}]).status_code == 409
    assert client.post(f'/api/orders/{oid}/cancel', headers=user1).status_code == 200
    assert client.post(f'/api/orders/{oid}/cancel', headers=user1).status_code == 409
    assert services.inventory.stock[1] == 10
    assert services.inventory.release_calls == 1
    assert [e['eventType'] for e in services.published] == ['OrderCreated', 'OrderCancelled']
    assert all(e['payload']['orderId'] == oid and e['orderId'] == oid for e in services.published)


def test_grpc_unavailable(grpc_inventory, make_order):
    grpc_inventory.stop(0).wait()
    response = make_order()
    assert response.status_code == 503
    assert 'message' in response.json()


def test_kafka_failure_does_not_raise(monkeypatch, caplog):
    from types import SimpleNamespace
    class Broken:
        def send(self, *args, **kwargs):
            raise RuntimeError('broker unavailable')
    monkeypatch.setattr(events, '_producer', Broken())
    events.publish('OrderCancelled', SimpleNamespace(id='1', user_id='u', total=10))
    assert 'Kafka publication failed' in caplog.text

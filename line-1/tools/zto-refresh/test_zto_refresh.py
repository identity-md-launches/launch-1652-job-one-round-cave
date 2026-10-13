import contextlib
import copy
import io
import json
import unittest
from unittest.mock import patch

import zto_refresh as refresh


class RefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.obs = refresh.path.read_json(str(refresh.SNAPSHOT))
        cls.evidence = refresh.path.read_json(str(refresh.EVIDENCE))

    def test_real_state_round_trip_on_new_ephemeral_port(self):
        table = refresh.replay_table(self.obs, self.evidence)
        cases = [(r['input_token'], r['amount']) for r in self.evidence['results']]
        with refresh.replay_relay(table) as (endpoint, requests):
            obs, check = refresh.refresh(endpoint, self.obs['base']['block']['number'], 1, cases)
        self.assertEqual(obs['base']['source'], endpoint)
        self.assertEqual(check['source'], endpoint)
        expected = copy.deepcopy(self.obs)
        expected['base']['source'] = endpoint
        self.assertEqual(obs, expected)
        self.assertTrue(check['all_match'])
        self.assertEqual(len(check['results']), 11)
        self.assertTrue(requests)
        for request in requests:
            self.assertIn(request['method'], refresh.path.z.RPC.METHODS)
            if request['method'] == 'eth_call':
                self.assertEqual(request['params'][1], {
                    'blockHash': self.obs['base']['block']['hash'], 'requireCanonical': True})

    def test_relay_does_not_claim_public_upstream(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(refresh.main([]), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['mode'], 'historical_local_http_replay')
        self.assertTrue(result['transport_endpoint'].startswith('http://127.0.0.1:'))
        self.assertEqual(result['archival_source'], self.obs['base']['source'])

    def test_endpoint_validation_never_connects(self):
        for url in ('https://ethereum-rpc.publicnode.com', 'https://eth.drpc.org',
                    'http://127.0.0.1:18001/rpc/1', 'http://[::1]:18002/rpc/1'):
            refresh.path.z.validate_endpoint(url)
        for url in ('http://example.com:80/rpc', 'http://192.168.0.1:80/rpc',
                    'http://localhost:80/rpc', 'http://127.0.0.1/rpc',
                    'http://127.0.0.1:0/rpc', 'http://127.0.0.1:65536/rpc',
                    'http://127.0.0.1:invalid/rpc', 'https://user:secret@example.com',
                    'https://example.com?key=secret', 'https://example.com#secret',
                    ' https://example.com', 'https://example.com\n', 'file:///x',
                    'https://', 'https://example.com?', 'https://example.com#', None):
            with self.subTest(url=url), self.assertRaises(ValueError):
                refresh.path.z.validate_endpoint(url)

    def test_send_methods_refused_before_any_request(self):
        rpc = refresh.path.z.RPC('http://127.0.0.1:18001/rpc/1')
        with patch.object(rpc.opener, 'open', side_effect=AssertionError('unexpected request')):
            for method in ('eth_sendRawTransaction', 'eth_sendTransaction', 'personal_sign',
                           'eth_sign', 'eth_getBalance'):
                with self.assertRaises(ValueError):
                    rpc.call(method, [])

    def test_redirect_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'redirects'):
            refresh.path.z.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere.example')

    def test_wrong_quoter_block_refused(self):
        bad = copy.deepcopy(self.evidence)
        bad['block']['hash'] = '0x' + '11' * 32
        with self.assertRaisesRegex(ValueError, 'match the snapshot block'):
            refresh.replay_table(self.obs, bad)

    def test_wrong_calldata_refused_despite_saved_true_verdict(self):
        bad = copy.deepcopy(self.evidence)
        bad['results'][0]['request']['data'] = '0x'
        with self.assertRaisesRegex(ValueError, 'calldata'):
            refresh.replay_table(self.obs, bad)

    def test_wrong_output_refused_despite_saved_true_verdict(self):
        bad = copy.deepcopy(self.evidence)
        case = bad['results'][1]
        case['raw_result'] = '0x' + (refresh.path.z.word(123) + refresh.path.z.word(0)).hex()
        with refresh.replay_relay(refresh.replay_table(self.obs, bad)) as (endpoint, _):
            with self.assertRaisesRegex(ValueError, 'disagrees'):
                refresh.refresh(endpoint, self.obs['base']['block']['number'], 1, [('ZTO', '1')])

    def test_changed_header_refuses_capture(self):
        table = refresh.replay_table(self.obs, self.evidence)
        key = json.dumps(['eth_getBlockByNumber', [self.obs['base']['block']['number'], False]], sort_keys=True)
        count = [0]
        original = refresh.path.z.RPC.call

        def call(rpc, method, params):
            result = original(rpc, method, params)
            if json.dumps([method, params], sort_keys=True) == key:
                count[0] += 1
                if count[0] > 1:
                    return dict(result, hash='0x' + '22' * 32)
            return result

        with refresh.replay_relay(table) as (endpoint, _), patch.object(refresh.path.z.RPC, 'call', call):
            with self.assertRaisesRegex(ValueError, 'block changed'):
                refresh.refresh(endpoint, self.obs['base']['block']['number'], 1, [('ZTO', '1')])

    def test_malformed_envelope_refused(self):
        rpc = refresh.path.z.RPC(refresh.path.z.PUBLIC_RPC)
        for payload in ({'jsonrpc': '2.0', 'id': 900, 'result': '0x1'},
                        {'jsonrpc': '2.0', 'id': 1, 'error': {'message': 'unavailable'}}):
            rpc.counter = 0
            with patch.object(rpc.opener, 'open', return_value=io.BytesIO(json.dumps(payload).encode())):
                with self.assertRaises(ValueError):
                    rpc.call('eth_chainId', [])


if __name__ == '__main__':
    unittest.main()

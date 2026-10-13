"""Offline transport boundary and provenance tests; never contacts a network."""
import contextlib
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import relay_rehearsal as tool

r = tool.core
RELAY = 'http://127.0.0.1:41965/rpc/1'


class RelayTests(unittest.TestCase):
    def test_relay_separates_transport_from_attribution(self):
        rpc = r.RPC(r.ENDPOINTS[0], relay=RELAY)
        self.assertEqual(rpc.endpoint, r.ENDPOINTS[0])
        response = io.BytesIO(b'{"jsonrpc":"2.0","id":1,"result":"0x1"}')
        with patch.object(rpc.opener, 'open', return_value=response) as opened:
            self.assertEqual(rpc.call('eth_chainId', []), '0x1')
        request = opened.call_args.args[0]
        self.assertEqual(request.full_url, RELAY)
        self.assertEqual(json.loads(request.data)['method'], 'eth_chainId')
        self.assertIn('Pepeolithic', request.get_header('User-agent'))

    def test_bad_routes_rejected_before_opener_creation(self):
        bad = ['http://localhost:123/rpc/1', 'https://127.0.0.1:123/rpc/1',
               'http://127.0.0.1:0/rpc/1', 'http://127.0.0.1:65536/rpc/1',
               'http://127.0.0.1:123/rpc/56', RELAY + '?key=x', RELAY + '#x',
               'http://user:pass@127.0.0.1:123/rpc/1', 'file:///etc/passwd',
               'http://127.0.0.1:123/rpc/1/../send', 'http://example.com/rpc/1']
        with patch.object(r.urllib.request, 'build_opener') as opener:
            for route in bad:
                with self.subTest(route=route), self.assertRaises(ValueError):
                    r.RPC(r.ENDPOINTS[0], relay=route)
            opener.assert_not_called()

    def test_dynamic_port_and_public_attribution_allowlist(self):
        for port in (1, 49152, 65535):
            self.assertTrue(r.RPC(r.ENDPOINTS[0], relay=f'http://127.0.0.1:{port}/rpc/1').via_relay)
        with self.assertRaises(ValueError):
            r.RPC('https://unapproved.invalid', relay=RELAY)

    def test_relay_cannot_send_or_sign(self):
        rpc = r.RPC(r.ENDPOINTS[0], relay=RELAY)
        with patch.object(rpc.opener, 'open') as opened:
            for method in ('eth_sendTransaction', 'eth_sendRawTransaction', 'eth_sign',
                           'personal_sign', 'eth_accounts', 'debug_traceCall'):
                with self.subTest(method=method), self.assertRaises(ValueError):
                    rpc.call(method, [])
            opened.assert_not_called()

    def test_direct_default_remains_direct(self):
        rpc = r.RPC(r.ENDPOINTS[1])
        self.assertEqual(rpc.transport, r.ENDPOINTS[1])
        self.assertFalse(rpc.via_relay)

    def test_redirect_stays_forbidden(self):
        with self.assertRaisesRegex(ValueError, 'redirect'):
            r.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com')

    def test_live_saved_observation_has_no_private_route(self):
        raw = (Path(__file__).parent / 'zto-relay-observation.json').read_text()
        obs = json.loads(raw)
        result = r.report(obs)
        self.assertEqual(result['call']['to'], r.TOKENS['ZTO'])
        self.assertEqual(result['result']['uint256'], '1000000000000000000000000000')
        self.assertTrue(result['transport']['source_is_attribution_only'])
        self.assertFalse(result['transport']['independent_provider_verified'])
        self.assertNotIn('127.0.0.1', raw)
        self.assertIn('not verified', result['limits'])

    def test_bad_provenance_rejected(self):
        obs = json.loads((Path(__file__).parent / 'zto-relay-observation.json').read_text())
        for key, value in [('independent_provider_verified', True),
                           ('independent_provider_verified', 0),
                           ('source_is_attribution_only', False),
                           ('source_is_attribution_only', 1), ('kind', 'public-direct')]:
            altered = copy.deepcopy(obs)
            altered['transport'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                r.report(altered)

    def test_demo_cannot_network(self):
        with patch.object(r.RPC, 'call', side_effect=AssertionError('network forbidden')), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(tool.main(['demo']), 0)
        self.assertEqual(json.loads(output.getvalue())['result']['status'], 'returned')

    def test_cli_passes_explicit_relay(self):
        with patch.object(r, 'main', return_value=0) as main:
            self.assertEqual(tool.main(['live', '--relay', RELAY]), 0)
        self.assertEqual(main.call_args.args[0],
                         ['demo', '--relay', RELAY, '--rpc', r.ENDPOINTS[0], '--token', 'ZTO'])


if __name__ == '__main__':
    unittest.main()

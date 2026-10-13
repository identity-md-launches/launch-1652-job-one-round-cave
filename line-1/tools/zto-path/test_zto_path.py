"""Offline regression and boundary tests. Synthetic cases are explicitly named."""
import contextlib
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import zto_path as p
from math_core import capacity, sqrt_at_tick

HERE = Path(__file__).resolve().parent


def synthetic(tick=0, price=None, liquidity=1_000_000, entries=None):
    """Test-only state; never an RPC observation or a deliverable example."""
    obs = copy.deepcopy(p.read_json(str(HERE/'observation.json')))
    if entries is None:
        entries = {-120: (1_000_000, 1_000_000), 60: (1_000_000, 1_000_000),
                   120: (2_000_000, -2_000_000)}
    base = obs['base']
    base['raw']['slot0'] = '0x'+b''.join(p.z.word(x) for x in (
        sqrt_at_tick(tick) if price is None else price, tick, 0, 12500)).hex()
    base['raw']['liquidity'] = '0x'+p.z.word(liquidity).hex()
    center = tick//60//256
    bitmap = {i: 0 for i in range(center-1,center+2)}
    for edge in entries:
        word, bit = divmod(edge//60,256)
        bitmap[word] |= 1 << bit
    obs['bitmap'] = {str(k):'0x'+p.z.word(v).hex() for k,v in bitmap.items()}
    obs['ticks'] = {str(k):'0x'+p.z.word(g).hex()+p.z.word(n).hex()
                    for k,(g,n) in entries.items()}
    return obs


class PathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.obs = p.read_json(str(HERE/'observation.json'))

    def test_real_quoter_outputs_and_calldata(self):
        evidence = p.read_json(str(HERE/'quoter-check.json'))
        self.assertEqual(evidence['block'],self.obs['base']['block'])
        self.assertEqual(len(evidence['results']),11)
        self.assertTrue(evidence['all_match'])
        saw_word_transition = False
        for case in evidence['results']:
            q = p.quote(self.obs,case['input_token'],case['amount'])
            self.assertEqual(q['status'],'estimated')
            self.assertEqual(q['estimate']['output_raw'],str(p.z.words(case['raw_result'],2)[0]))
            self.assertEqual(q['estimate']['input_unspent_raw'],'0')
            self.assertTrue(case['matches'])
            self.assertEqual(case['request']['to'],p.QUOTER)
            calldata = case['request']['data']
            self.assertEqual(calldata[:10],p.selector('quoteExactInputSingle(((address,address,uint24,int24,address),bool,uint128,bytes))'))
            words = p.z.words('0x'+calldata[10:],10)
            self.assertEqual(words[6],int(case['input_token']=='IMD'))
            self.assertEqual(words[7],int(q['requested_input_raw']))
            saw_word_transition |= len(q['steps'])>1
        self.assertTrue(saw_word_transition)

    def test_real_improvement_over_one_interval(self):
        self.assertEqual(p.z.report(self.obs['base'],'ZTO','100000000')['status'],'outside_interval')
        self.assertEqual(p.quote(self.obs)['estimate']['output'],'1196.130391948897309582')

    def test_real_exhaustion_is_not_full_fill(self):
        q = p.quote(self.obs,'ZTO','1000000000')
        self.assertEqual(q['status'],'outside_coverage')
        self.assertNotIn('estimate',q)
        self.assertEqual(q['initialized_ticks_crossed'],1)
        self.assertEqual(q['partial']['liquidity_after_raw'],'0')
        self.assertGreater(int(q['partial']['input_unspent_raw']),0)
        self.assertEqual(int(q['partial']['input_unspent_raw'])+int(q['partial']['input_consumed_raw']),10**27)

    def test_negative_bitmap_and_inclusive_downward_search(self):
        bits = {-1:1<<255,0:1|1<<1}
        self.assertEqual(p.next_boundary(bits,-1,60,True),(-60,True))
        self.assertEqual(p.next_boundary(bits,-1,60,False),(0,True))
        self.assertEqual(p.next_boundary(bits,0,60,True),(0,True))
        self.assertEqual(p.next_boundary(bits,0,60,False),(60,True))
        self.assertEqual(p.next_boundary({-1:0},-61,60,True),(-15360,False))
        self.assertIsNone(p.next_boundary({},0,60,True))

    def test_synthetic_upward_crossing_adds_liquidity(self):
        obs = synthetic()
        cap = capacity(sqrt_at_tick(0),sqrt_at_tick(60),1_000_000,12500,False)
        q = p.quote(obs,'ZTO',p.z.units(cap+100,18))
        self.assertEqual(q['status'],'estimated')
        self.assertEqual(q['initialized_ticks_crossed'],1)
        self.assertEqual(q['steps'][0]['liquidity_after_raw'],'2000000')
        self.assertEqual(q['steps'][1]['liquidity_before_raw'],'2000000')
        self.assertEqual(sum(int(s['input_consumed_raw']) for s in q['steps']),cap+100)

    def test_synthetic_downward_crossing_subtracts_signed_net(self):
        obs = synthetic(tick=90,liquidity=2_000_000)
        cap = capacity(sqrt_at_tick(90),sqrt_at_tick(60),2_000_000,12500,True)
        q = p.quote(obs,'IMD',p.z.units(cap+100,18))
        self.assertEqual(q['status'],'estimated')
        self.assertEqual(q['steps'][0]['liquidity_after_raw'],'1000000')
        self.assertEqual(q['initialized_ticks_crossed'],1)

    def test_synthetic_boundary_no_double_crossing(self):
        # Upward recross after a prior downward crossing at tick 60.
        obs = synthetic(tick=59,price=sqrt_at_tick(60))
        q = p.quote(obs,'ZTO',p.z.units(100,18))
        self.assertEqual(q['steps'][0]['input_consumed_raw'],'0')
        self.assertEqual(q['steps'][0]['liquidity_after_raw'],'2000000')
        self.assertEqual(q['initialized_ticks_crossed'],1)
        # Inclusive downward crossing when price is exactly at tick 60.
        obs = synthetic(tick=60,liquidity=2_000_000)
        q = p.quote(obs,'IMD',p.z.units(100,18))
        self.assertEqual(q['steps'][0]['input_consumed_raw'],'0')
        self.assertEqual(q['initialized_ticks_crossed'],1)
        self.assertEqual(q['estimate']['liquidity_after_raw'],'1000000')

    def test_synthetic_known_zero_liquidity_gap(self):
        obs = synthetic(liquidity=0,entries={60:(1000000,1000000),120:(1000000,-1000000)})
        q = p.quote(obs,'ZTO',p.z.units(100,18))
        self.assertEqual(q['status'],'estimated')
        self.assertEqual(q['steps'][0]['input_consumed_raw'],'0')
        self.assertEqual(q['steps'][0]['output_raw'],'0')
        self.assertGreater(int(q['estimate']['output_raw']),0)

    def test_synthetic_empty_range_refuses_at_coverage(self):
        q = p.quote(synthetic(liquidity=0,entries={}),amount='1')
        self.assertEqual(q['status'],'outside_coverage')
        self.assertEqual(q['partial']['input_consumed_raw'],'0')
        self.assertLess(len(q['steps']),10)

    def test_exactly_consumed_at_boundary_crosses_once(self):
        cap = capacity(sqrt_at_tick(0),sqrt_at_tick(60),1000000,12500,False)
        q = p.quote(synthetic(),'ZTO',p.z.units(cap,18))
        self.assertEqual(q['status'],'estimated')
        self.assertEqual(len(q['steps']),1)
        self.assertEqual(q['estimate']['tick_after'],60)
        self.assertEqual(q['initialized_ticks_crossed'],1)

    def test_step_limit_has_no_estimate(self):
        q = p.quote(self.obs,'ZTO','500000000',max_steps=1)
        self.assertEqual(q['status'],'step_limit')
        self.assertNotIn('estimate',q)
        for value in (0,257,True):
            with self.assertRaises(ValueError): p.quote(self.obs,max_steps=value)

    def test_corrupted_bitmap_tick_and_liquidity_rejected(self):
        mutations = [lambda o:o['bitmap'].pop(next(iter(o['bitmap']))),
                     lambda o:o['ticks'].clear(),
                     lambda o:o['ticks'].update({'1':'0x'+p.z.word(1).hex()*2}),
                     lambda o:o.update(word_radius=True),
                     lambda o:o['bitmap'].update({'7':'0x12'}),
                     lambda o:o['ticks'].update({'128940':'0x'+p.z.word(1).hex()+p.z.word(2).hex()}),
                     lambda o:o['ticks'].update({'128940':'0x'+p.z.word(0).hex()*2})]
        for mutate in mutations:
            obs=copy.deepcopy(self.obs); mutate(obs)
            with self.assertRaises(ValueError): p.decode(obs)

    def test_synthetic_liquidity_underflow_rejected(self):
        obs = synthetic(entries={60:(2000000,-2000000)})
        with self.assertRaisesRegex(ValueError,'liquidity after crossing'):
            p.quote(obs,amount='1')

    def test_monotonicity_and_conservation(self):
        for token in ('ZTO','IMD'):
            previous = 0
            for raw in (1,2,999,10**12,10**18,10**19):
                q = p.quote(self.obs,token,p.z.units(raw,18))
                self.assertEqual(q['status'],'estimated')
                e = q['estimate']
                self.assertGreaterEqual(int(e['output_raw']),previous)
                previous = int(e['output_raw'])
                self.assertEqual(int(e['input_consumed_raw'])+int(e['input_unspent_raw']),raw)
                self.assertEqual(sum(int(s['fee_raw']) for s in q['steps']),int(e['fee_raw']))
                self.assertTrue(0<=int(e['fee_raw'])<=raw)

    def test_live_capture_hash_pinning_and_reorg(self):
        obs=self.obs; calls=[]
        class FakeRPC:
            reorg=False
            def __init__(self, endpoint): pass
            def call(self,method,params):
                calls.append((method,params))
                if method=='eth_chainId': return '0x1'
                if method=='eth_getBlockByNumber':
                    return dict(obs['base']['block'],hash='changed') if self.reorg else obs['base']['block']
                data=params[0]['data']; value=p.z.signed(int(data[-64:],16),24)
                if data.startswith(p.selector('getTickBitmap(bytes32,int16)')):
                    return obs['bitmap'][str(value)]
                return obs['ticks'][str(value)]
        with patch.object(p.z,'capture',return_value=obs['base']),patch.object(p.z,'RPC',FakeRPC):
            self.assertEqual(p.capture(p.z.PUBLIC_RPC),obs)
            for method,params in calls:
                if method=='eth_call': self.assertEqual(params[1],{'blockHash':obs['base']['block']['hash'],'requireCanonical':True})
            FakeRPC.reorg=True
            with self.assertRaisesRegex(ValueError,'block changed'): p.capture(p.z.PUBLIC_RPC)

    def test_offline_cli_and_invalid_input(self):
        with patch.object(p.z,'RPC',side_effect=AssertionError('network forbidden')):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(p.main(['--snapshot',str(HERE/'observation.json')]),0)
            self.assertEqual(json.loads(output.getvalue())['status'],'estimated')
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(p.main(['--snapshot',str(HERE/'observation.json'),'--amount','1000000000']),2)
            self.assertNotIn('estimate',json.loads(output.getvalue()))
        for token,amount in [('OTHER','1'),('ZTO','0'),('ZTO','-1'),('ZTO','1e9'),('ZTO',str(1<<127))]:
            with self.assertRaises(ValueError): p.quote(self.obs,token,amount)

    def test_current_relay_and_read_only_allowlist(self):
        p.z.RPC('http://127.0.0.1:34689/rpc/1')
        # Explicit loopback routes remain valid when the next machine changes port.
        p.z.RPC('http://127.0.0.1:34793/rpc/1')
        with self.assertRaises(ValueError): p.z.RPC('http://192.168.0.1:34793/rpc/1')
        with self.assertRaises(ValueError): p.z.RPC(p.z.PUBLIC_RPC).call('eth_sendTransaction',[])
        with self.assertRaises(ValueError): p.z.RPC('https://user:pass@example.com')


if __name__=='__main__': unittest.main()

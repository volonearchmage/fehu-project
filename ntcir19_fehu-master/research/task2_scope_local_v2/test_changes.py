"""Focused checks of newly changed behavior, not a repeat of 47 v1 tests."""
from dataclasses import replace
import json
import unittest

import numpy as np
import torch

from research.task2_scope_local_v1.data import Bag, Event, load_json
from research.task2_scope_local_v1.losses import scope_loss
from research.task2_scope_local_v1.prepare import PROJECT
from .inputs import BagTokenizer, V1, render
from .metrics import exact_scan, at_threshold
from .score import export


class ChangedBehavior(unittest.TestCase):
    def test_threshold_ties_empty_and_bruteforce(self):
        for scores, labels in (([.2,.2,.1,.05], [1,0,1,0]), ([0.,1.,1.], [0,0,0]),
                               ([.50000001,.5,.1], [1,0,1])):
            s=np.array(scores, dtype=np.float32); y=np.array(labels)
            selected, _ = exact_scan(s,y)
            brute=max((at_threshold(s,y,float(t)) for t in [2., *set(s.tolist())]), key=lambda r:(r['micro_f1'],r['threshold']))
            self.assertEqual(selected, brute)
            self.assertEqual(selected, at_threshold(s,y,json.loads(json.dumps(selected['threshold']))))
        self.assertEqual(exact_scan([1., 0.], [0,0])[0]['threshold'], 2.)

    def test_ids_cannot_affect_render_or_token_scopes(self):
        b=Bag('opaque-guid','opaque-actor','Alice','Alice protects the forest.',(Event('opaque-event','The forest is protected.'),))
        changed=replace(b,guid='different',actor_id='unrelated',events=(replace(b.events[0],id='new'),))
        self.assertEqual(render(b),render(changed))
        tok=BagTokenizer(PROJECT/'.cache/task2_scope_local_v1/tokenizer/8949b909ec900327062f0ebf497f51aef5e6f0c8',load_json(V1/'tokenizer_lock.json'))
        x,z=tok.encode(b),tok.encode(changed)
        self.assertEqual(x.input_ids,z.input_ids); self.assertEqual(x.scope_indices,z.scope_indices)
        self.assertNotEqual(x.event_ids,z.event_ids)

    def test_T_has_event_gradient_and_zero_article_logit_gradient(self):
        a=torch.tensor([[.3,-.2]],requires_grad=True)
        c=torch.tensor([[[.1,.8],[-.4,.5]]],requires_grad=True)
        result=scope_loss(a,c,torch.tensor([[1.,0.]]),torch.tensor([[[1.,0.],[0.,0.]]]),torch.ones((1,2),dtype=torch.bool),mode='J',article_weight=0.)
        result['loss'].backward()
        self.assertEqual(a.grad.abs().sum().item(),0.)
        self.assertGreater(c.grad.abs().sum().item(),0.)

    def test_export_precision_and_all_empty(self):
        s=np.zeros((2,108),dtype=np.float32); s[0,0]=np.float32(.2);s[1,0]=s[0,0]
        rows=[dict(guid='g',actor_id='a',event_ids=['e1','e2'],article_probability=[1.]*108,event_probability=s.tolist())]
        mapping={str(i):str(i%20) for i in range(54)}
        threshold=json.loads(json.dumps(float(s[0,0])))
        out=export(rows,mapping,threshold)
        self.assertEqual(sum(len(e['subevent_human_values']) for a in out['task2b'] for e in a['subevents_human_values']),2)
        empty=export(rows,mapping,2.)
        self.assertEqual(empty['coverage']['candidates'],2)
        self.assertTrue(all(not e['subevent_human_values'] for a in empty['task2b'] for e in a['subevents_human_values']))


if __name__ == '__main__': unittest.main()

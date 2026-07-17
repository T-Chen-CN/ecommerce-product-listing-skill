import copy, json, subprocess, sys, tempfile, unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; C=ROOT/'scripts/delivery_config.py'; M=ROOT/'scripts/run_manifest.py'
def cli(script,*args): return subprocess.run([sys.executable,str(script),*map(str,args)],text=True,capture_output=True)
class ReviewBypassTest(unittest.TestCase):
 def boot(self,td,route='docx'):
  p=Path(td)/'config.json'; expiry=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
  r=cli(C,'bootstrap','--config',p,'--delivery-route',route,'--capability-version','v1','--expires-at',expiry);self.assertEqual(r.returncode,0,r.stderr);return p
 def init(self,td,route='docx',scope='content'):
  c=self.boot(td,route);p=Path(td)/'run.json';a=['init',p,'--delivery-config',c,'--task-scope',scope,'--requested-module','title','--target-language','zh-CN']
  if route=='docx':a+=['--agent-name','Agent','--product-name','Widget','--country-code','US']
  r=cli(M,*a);self.assertEqual(r.returncode,0,r.stderr);return p
 def test_manifest_consumes_config_not_handwritten_result(self):
  with tempfile.TemporaryDirectory() as td:
   fake=Path(td)/'fake.json';fake.write_text(json.dumps({'delivery_route':'docx','delivery_route_source':'bootstrap_result','delivery_config_schema_version':1,'delivery_override':None}))
   r=cli(M,'init',Path(td)/'m.json','--delivery-config',fake);self.assertNotEqual(r.returncode,0)
   r=cli(M,'init',Path(td)/'x.json','--delivery-config',fake,'--delivery-route-file',fake);self.assertNotEqual(r.returncode,0);self.assertIn('unrecognized arguments',r.stderr)
 def test_create_only_and_concurrent_routes_exactly_one_success(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'c.json';expiry=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
   def go(route):return cli(C,'bootstrap','--config',p,'--delivery-route',route,'--capability-version','v1','--expires-at',expiry).returncode
   with ThreadPoolExecutor(max_workers=2) as pool: codes=list(pool.map(go,['docx','interactive_card']))
   self.assertEqual(sorted(codes),[0,2]); good=p.read_bytes()
   self.assertEqual(go('docx'),2);self.assertEqual(p.read_bytes(),good)
   p.write_text('{bad');self.assertEqual(go('docx'),0)
 def test_closed_evidence_and_time_pair(self):
  with tempfile.TemporaryDirectory() as td:
   p=self.boot(td);base=json.loads(p.read_text());e=base['bootstrap_evidence'];self.assertEqual(set(e),{'evidence_version','capability_version','docx_capable','interactive_card_capable','verified_at','expires_at'})
   cases=[]
   for mutate in (lambda x:x['bootstrap_evidence'].__setitem__('free_text','x'),lambda x:x['bootstrap_evidence'].__setitem__('verified_at','2026-01-01T00:00:00'),lambda x:x['bootstrap_evidence'].pop('expires_at'),lambda x:x['bootstrap_evidence'].__setitem__('expires_at',x['bootstrap_evidence']['verified_at'])):
    x=copy.deepcopy(base);mutate(x);cases.append(x)
   for i,x in enumerate(cases):
    q=Path(td)/f'b{i}.json';q.write_text(json.dumps(x));self.assertNotEqual(cli(M,'init',Path(td)/f'm{i}.json','--delivery-config',q).returncode,0)
 def test_content_card_needs_card_and_forbids_all_docx_evidence(self):
  with tempfile.TemporaryDirectory() as td:
   p=self.init(td,'interactive_card');d=json.loads(p.read_text());d['modules']['title']={'source_text':'标题','render_text':'标题'};d['status']='ready';d['delivery']['card']={'message_id':'om_fixture','send_success':True};p.write_text(json.dumps(d));self.assertEqual(cli(M,'validate',p,'--delivery').returncode,0)
   for key,val in [('docx',{'token':'docx_x','permalink':'https://docs.feishu.cn/docx/docx_x'}),('folder',{'token':'folder_x','permalink':'https://docs.feishu.cn/drive/folder/folder_x'}),('directory_chain',[]),('product_folder_token','folder_x')]:
    x=copy.deepcopy(d);x['delivery'][key]=val;p.write_text(json.dumps(x));self.assertNotEqual(cli(M,'validate',p,'--delivery').returncode,0,key)
 def test_docx_forbids_card_evidence(self):
  with tempfile.TemporaryDirectory() as td:
   p=self.init(td,'docx');d=json.loads(p.read_text());d['delivery']['card']={'message_id':'om_fixture','send_success':True};p.write_text(json.dumps(d));self.assertNotEqual(cli(M,'validate',p).returncode,0)
 def test_v7_to_v8_and_invalid_v8_reinit(self):
  with tempfile.TemporaryDirectory() as td:
   c=self.boot(td);p=Path(td)/'m.json';p.write_text(json.dumps({'schema_version':7,'generation':4,'revision':9}));args=['init',p,'--delivery-config',c,'--force','--agent-name','Agent','--product-name','Widget','--country-code','US'];self.assertEqual(cli(M,*args).returncode,0);d=json.loads(p.read_text());self.assertEqual((d['schema_version'],d['generation'],d['revision']),(8,5,10));self.assertNotEqual(cli(M,*args).returncode,0);d['evil']=1;p.write_text(json.dumps(d));self.assertEqual(cli(M,*args).returncode,0)
if __name__=='__main__':unittest.main()

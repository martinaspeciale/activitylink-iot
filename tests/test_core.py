import unittest,json
from backend.core import validate,decide
class CoreTests(unittest.TestCase):
 def test_valid(self):
  m=dict(node='node1',boot='0123456789abcdef',seq=1,uptime=1,activity=1,enabled=1,led=1)
  self.assertEqual(validate('activitylink/node1/telemetry',json.dumps(m))['seq'],1)
  m['enabled']=0
  with self.assertRaises(ValueError):validate('activitylink/node1/telemetry',json.dumps(m))
 def test_wrong_topic(self):
  with self.assertRaises(ValueError):validate('activitylink/x/telemetry','{}')
 def test_adaptation(self):
  row=dict(received=0,enabled=1,activity=1)
  self.assertEqual(decide(row,7,True),(3,True))
  self.assertEqual(decide(row,7,False),(1,True))
  self.assertEqual(decide(row,2,True),(1,False))
 def test_pause_and_absence(self):
  self.assertEqual(decide(dict(received=1,enabled=0,activity=0),2,True),(0,False))
  self.assertEqual(decide(None,2,False),(3,True))
if __name__=='__main__':unittest.main()

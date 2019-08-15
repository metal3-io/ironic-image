from suds.client import Client

url = 'http://127.0.0.1:8080/ws/api.wsdl'

client = Client(url, cache=None)

print client

print client.service.multiply(4, 5)
print client.service.helloworld()
print client.service.getperson()
p = client.service.listpersons()
print repr(p)
p = client.service.setpersons(p)
print repr(p)

p = client.factory.create('ns0:Person')
p.id = 4
print p

a = client.factory.create('ns0:Person_Array')
print a

a = client.service.setpersons(a)
print repr(a)

a.item.append(p)
print repr(a)

a = client.service.setpersons(a)
print repr(a)


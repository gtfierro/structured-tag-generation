import json
from rdflib import Graph, Namespace, URIRef, Literal
from collections import defaultdict
import itertools

defs = json.load(open('defs.json'))

phiot = defs[1]

kinds_by_name = {x['name']: x for x in phiot['kinds']}

RDF = Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
RDFS = Namespace('http://www.w3.org/2000/01/rdf-schema#')
BRICK = Namespace('https://brickschema.org/schema/1.0.3/Brick#')
BRICKFRAME = Namespace('https://brickschema.org/schema/1.0.3/BrickFrame#')
BF = Namespace('https://brickschema.org/schema/1.0.3/BrickFrame#')
OWL = Namespace('http://www.w3.org/2002/07/owl#')
G = Graph()
G.bind('rdf', RDF)
G.bind('rdfs', RDFS)
G.bind('brick', BRICK)
G.bind('bf', BRICKFRAME)

pfx = """PREFIX rdf: <{0}>
       PREFIX owl: <{1}>
       PREFIX bf: <{2}>""".format(RDF,OWL, BRICKFRAME)
def query(q):
    return G.query(pfx+q)

def getValue(uri):
    return uri.split('#')[-1]

# set up superkind -> kind class relationships
parentChildRelships = []
for kindname, kinddef in kinds_by_name.items():
    parentChildRelships.append({'parent': kinddef['superkind'].split('::')[-1], 'child': kindname})

# insert this into the graph
for relship in parentChildRelships:
    G.add((BRICK[relship['child']], RDFS.subClassOf, BRICK[relship['parent']]))

# set up tags and traits associated with classes
for kindname, kinddef in kinds_by_name.items():
    for tagdef in kinddef.get('tags',[]):
        if tagdef['kind'] == 'ph::Marker':
            G.add((BRICK[kindname], BF.hasTag, BRICK[tagdef['name']]))
    for trait in kinddef.get('traits',[]):
        G.add((BRICK[kindname], BF.hasTrait, BRICK[trait.split('::')[-1]]))
    if 'traits' in kinddef:
        print(kindname, kinddef.get('traits'))


# point kinds (sensor, cmd, sp)
res = query("""
SELECT ?tag WHERE {
    brick:PointType bf:hasTag ?tag
}
""")
tagtypes = [getValue(x[0]) for x in res]

# creates classes with the tags of traits arranged in the given order
# TODO: use tag subsets to tell which are subclasses of which; for example,
#  the first waterpoint row below is superclasses of the second waterpoint row
#  because it generates tagsets that are strict subsets of the second row's
orders = [
    ('WaterPoint', ['WaterType', 'water', 'WaterPointQuantity']),
    ('WaterPoint', ['WaterPointSection', 'WaterType', 'water', 'WaterPointQuantity']),
    ('AirPoint', ['AirPointSection', 'air', 'AirPointQuantity']),
    ('AirPoint', ['air', 'AirPointQuantity']),
    ('ElecPoint', ['elec', 'ElecPointQuantity']),
    ('Meter', ['meter', 'MeterScope']),
    ('WaterMeter', ['WaterType', 'water', 'meter']),
    ('WaterTank', ['WaterType', 'water', 'tank']),
]

for pair in orders:
    name, order = pair
    res = query("""SELECT ?trait ?tag WHERE { brick:%s bf:hasTrait ?trait . ?trait bf:hasTag ?tag }""" % name)
    dd = defaultdict(list)
    for row in res:
        trait=getValue(row[0])
        dd[trait].append(getValue(row[1]))
    combos = [dd.get(item, [item]) for item in order]
    combos.append(tagtypes)
    tagsets = itertools.product(*combos) # preserves order
    for tagset in tagsets:
        print(name,tagset)
        tagsetname = '_'.join(tagset)
        G.add((BRICK[tagsetname], RDFS.subClassOf, BRICK[name]))
        for tag in tagset:
            G.add((BRICK[tagsetname], BF.hasTag, BRICK[tag]))
    
# for all classes, need to inherit the tags of the superkind

            
G.serialize('triples.n3',format='n3')

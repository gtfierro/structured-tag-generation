import json
from rdflib import Graph, Namespace, URIRef, Literal
from collections import defaultdict
import itertools

# convenience methods for working with the RDF graph
RDF = Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#')
RDFS = Namespace('http://www.w3.org/2000/01/rdf-schema#')
BRICK = Namespace('https://brickschema.org/schema/1.0.3/Brick#')
BRICKFRAME = Namespace('https://brickschema.org/schema/1.0.3/BrickFrame#')
BF = Namespace('https://brickschema.org/schema/1.0.3/BrickFrame#')
OWL = Namespace('http://www.w3.org/2002/07/owl#')
G = Graph()
G.bind('rdf', RDF)
G.bind('rdfs', RDFS)
G.bind('owl', OWL)
G.bind('brick', BRICK)
G.bind('bf', BRICKFRAME)

pfx = """PREFIX rdf: <{0}>
       PREFIX owl: <{1}>
       PREFIX bf: <{2}>""".format(RDF,OWL, BRICKFRAME)

def query(q):
    return G.query(pfx+q)

def getValue(uri):
    return uri.split('#')[-1]

############ START PROCESSING #############

# open the defs file
defs = json.load(open('defs.json'))

# only dealing with phIoT for now; these are points, equipment, etc
phiot = defs[1]

# turn phiot into a dict so we can look up definitions by name
kinds_by_name = {x['name']: x for x in phiot['kinds']}

### new definitions
# - BF.hasDefinition (object is a rdf literal)
# - BF.hasTrait (object is anther 'class')
# - BF.hasTag
# - BRICK.tag
# - BRICK.trait

# want to RDF-ify each of the kinds defined in 'defs'
for kindname, kinddef in kinds_by_name.items():
    # instantiate the 'name' as a class
    classname = kindname
    G.add((BRICK[classname], RDF.type, OWL.Class))
    if 'doc' in kinddef:
        G.add((BRICK[classname], BF.hasDefinition, Literal(kinddef.get('doc'))))

    # remove handle the namespace 'ph' or 'phiot' from the definition
    parentclass = kinddef['superkind'].split('::')[-1]
    # add the parentclass relationship
    G.add((BRICK[parentclass], RDF.type, OWL.Class))
    G.add((BRICK[classname], RDFS.subClassOf, BRICK[parentclass]))

    # handle the tags
    for tag in kinddef.get('tags',[]):
        # only include marker tags for the ontology
        if tag['kind'] != 'ph::Marker': continue

        # define the tag
        tagname = tag['name'].capitalize()
        G.add((BRICK[tagname], RDF.type, BRICK.Tag))
        G.add((BRICK[classname], BF.hasTag, BRICK[tagname]))
        if 'doc' in tag:
            G.add((BRICK[tagname], BF.hasDefinition, Literal(tag.get('doc'))))

    # handle the traits
    for trait in kinddef.get('traits', []):
        traitname = trait.split('::')[-1]
        G.add((BRICK[classname], BF.hasTrait, BRICK[traitname]))
        G.add((BRICK[traitname], RDF.type, BRICK.Trait))

# get point kinds (sensor, cmd, sp)
res = query("""
SELECT ?tag WHERE {
    brick:PointType bf:hasTag ?tag
}
""")
tagtypes = [getValue(x[0]) for x in res]

# creates classes with the tags of traits arranged in the given order
orders = [
    ('WaterPoint', ['WaterPointSection', 'WaterType', 'Water', 'WaterPointQuantity']),
    ('AirPoint', ['AirPointSection', 'Air', 'AirPointQuantity']),
    ('ElecPoint', ['Elec', 'ElecPointQuantity']),
    ('Meter', ['Meter', 'MeterScope']),
    ('WaterMeter', ['WaterType', 'Water', 'Meter']),
    ('WaterTank', ['WaterType', 'Water', 'Tank']),
]

generatedclasses = []
for pair in orders:
    name, order = pair
    res = query("""SELECT ?trait ?tag WHERE {
        brick:%s bf:hasTrait ?trait .
        ?trait bf:hasTag ?tag .
    }""" % name)
    dd = defaultdict(list)
    for row in res:
        trait=getValue(row[0])
        dd[trait].append(getValue(row[1]))
    allcombos = [dd.get(item, [item]) for item in order]
    allcombos.append(tagtypes)


    #  use tag subsets to tell which are subclasses of which
    # Loops from the right-hand side of the list in 'orders', adding more tags
    # according to the trait order so we can generate the classes
    for idx in range(1,len(allcombos)+1):
        combos = allcombos[-idx:]
        tagsets = itertools.product(*combos) # preserves order
        for tagset in tagsets:
            tagsetname = ''.join(tagset)
            generatedclasses.append(tagsetname)
            G.add((BRICK[tagsetname], RDFS.subClassOf, BRICK[name]))

            # semi-hacky way to get the parent classes
            possible = []
            for genclass in generatedclasses:
                if tagsetname.endswith(genclass) and tagsetname != genclass:
                    possible.append(genclass)
            if len(possible):
                parent = max(possible, key=lambda x: len(x))
                G.add((BRICK[tagsetname], RDF.subClassOf, BRICK[parent]))

            # associate tags with the class
            for tag in tagset:
                G.add((BRICK[tagsetname], BF.hasTag, BRICK[tag]))

# TODO: apply tags from parent classes to child classes

G.serialize('triples.n3',format='n3')
print('G has {0} triples'.format(len(G)))

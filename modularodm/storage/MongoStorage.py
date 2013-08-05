import re
import logging

from ..storage import Storage
from ..storage import KeyExistsException
from ..query.queryset import MongoQuerySet

# From mongoengine.queryset.transform
COMPARISON_OPERATORS = ('ne', 'gt', 'gte', 'lt', 'lte', 'in', 'nin', 'mod',
                        'all', 'size', 'exists', 'not')
GEO_OPERATORS        = ('within_distance', 'within_spherical_distance',
                        'within_box', 'within_polygon', 'near', 'near_sphere',
                        'max_distance', 'geo_within', 'geo_within_box',
                        'geo_within_polygon', 'geo_within_center',
                        'geo_within_sphere', 'geo_intersects')
STRING_OPERATORS     = ('contains', 'icontains', 'startswith',
                        'istartswith', 'endswith', 'iendswith',
                        'exact', 'iexact')
CUSTOM_OPERATORS     = ('match',)
MATCH_OPERATORS      = (COMPARISON_OPERATORS + GEO_OPERATORS +
                        STRING_OPERATORS + CUSTOM_OPERATORS)

UPDATE_OPERATORS     = ('set', 'unset', 'inc', 'dec', 'pop', 'push',
                        'push_all', 'pull', 'pull_all', 'add_to_set',
                        'set_on_insert')

# Adapted from mongoengine.fields
def prepare_query_value(op, value):

    if op.lstrip('i') in ('startswith', 'endswith', 'contains', 'exact'):
        flags = 0
        if op.startswith('i'):
            flags = re.IGNORECASE
            op = op.lstrip('i')

        regex = r'%s'
        if op == 'startswith':
            regex = r'^%s'
        elif op == 'endswith':
            regex = r'%s$'
        elif op == 'exact':
            regex = r'^%s$'

        # escape unsafe characters which could lead to a re.error
        value = re.escape(value)
        value = re.compile(regex % value, flags)
    return value

class MongoStorage(Storage):

    _query_set_class = MongoQuerySet

    def __init__(self, db, collection):
        self.collection = collection
        self.store = db[self.collection]

    def find_all(self):
        return self.store.find()

    def find(self, *query):
        mongo_query = self._translate_query(*query)
        return self.store.find(mongo_query)

    def find_one(self, *query):
        mongo_query = self._translate_query(*query)
        return self.store.find_one(mongo_query)

    def get(self, schema, key):
        return self.store.find_one({schema._primary_name : key})

    def insert(self, schema, key, value):
        if schema._primary_name not in value:
            value = value.copy()
            value[schema._primary_name] = key
        self.store.insert(value)

    # todo: add mongo-style updating (allow updating multiple records at once)
    def update(self, schema, key, value):
        self.store.update(
            {schema._primary_name : key},
            value
        )

    def remove(self, *query):
        mongo_query = self._translate_query(*query)
        self.store.remove(mongo_query)

    def flush(self):
        pass

    def __repr__(self):
        return self.find_all()

    def _translate_query(self, *query):

        mongo_query = {}

        for part in query:

            attr, oper, valu = part.attr, part.oper, part.valu

            if oper == 'eq':

                mongo_query[attr] = valu

            elif oper in COMPARISON_OPERATORS:

                mongo_oper = '$' + oper
                mongo_query[attr] = {mongo_oper : valu}

            elif oper in STRING_OPERATORS:

                mongo_oper = '$regex'
                mongo_regex = prepare_query_value(oper, valu)
                mongo_query[attr] = {mongo_oper : mongo_regex}

        return mongo_query
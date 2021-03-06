import os
import logging
import dataset
from lxml import etree
from pprint import pprint
from sqlalchemy import select, and_

import requests.packages.urllib3

requests.packages.urllib3.disable_warnings()
logging.basicConfig(level=logging.INFO)
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('alembic').setLevel(logging.WARNING)


DATABASE_URI = os.environ.get('DATABASE_URI')
assert DATABASE_URI, "No database URI defined in DATABASE_URI."

DATA_PATH = os.environ.get('DATA_PATH')
assert DATA_PATH, "No data path defined in DATA_PATH."


engine = dataset.connect(DATABASE_URI)
documents_table = engine['eu_ted_documents']
contracts_table = engine['eu_ted_contracts']
references_table = engine['eu_ted_references']
cpvs_table = engine['eu_ted_cpvs']


def ted_contracts():
    contract_alias = contracts_table.table.alias('contract')
    document_alias = documents_table.table.alias('document')
    _tables = [contract_alias, document_alias]
    _filters = and_(contract_alias.c.doc_no == document_alias.c.doc_no)

    q = select(_tables, _filters, _tables, use_labels=True,
               order_by=[document_alias.c.doc_no.desc()])
    for contract in engine.query(q):
        yield contract


class Extractor(object):

    def __init__(self, el):
        self.el = el
        self.paths = {}
        self._ignore = set()
        self.generate(el)

    def element_name(self, el):
        if el == self.el:
            return '.'
        return self.element_name(el.getparent()) + '/' + el.tag

    def generate(self, el):
        children = el.getchildren()
        if len(children):
            for child in children:
                self.generate(child)
        else:
            name = self.element_name(el)
            if name not in self.paths:
                self.paths[name] = el

    def ignore(self, path):
        if path.endswith('*'):
            path = path[:len(path)-1]
            for p in self.paths.keys():
                if p.startswith(path):
                    self._ignore.add(p)
        else:
            self._ignore.add(path)

    def text(self, path, ignore=True):
        if path is None:
            return
        el = self.el.find(path)
        if el is None:
            return None
        if ignore:
            self.ignore(self.element_name(el))
        return el.text

    def html(self, path, ignore=True):
        if path is None:
            return
        el = self.el.find(path)
        if el is None:
            return None
        if ignore:
            self.ignore(self.element_name(el))
        return etree.tostring(el)

    def attr(self, path, attr, ignore=True):
        if path is None:
            return
        el = self.el.find(path)
        if el is None:
            return None
        if ignore:
            self.ignore(self.element_name(el))
        return el.get(attr)

    def audit(self):
        for k, v in sorted(self.paths.items()):
            if k in self._ignore:
                continue
            if v.text or len(v.attrib.keys()):
                pprint({
                    'path': k,
                    'text': v.text,
                    'attr': v.attrib
                })

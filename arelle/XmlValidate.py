'''
Created on Feb 20, 2011

@author: Mark V Systems Limited
(c) Copyright 2011 Mark V Systems Limited, All rights reserved.
'''
from lxml import etree
import xml.dom.minidom, os
from arelle import (XbrlConst, XmlUtil)
from arelle.ModelValue import (qname, dateTime, DATE, DATETIME)

UNKNOWN = 0
INVALID = 1
NONE = 2
VALID = 3
VALID_ID = 4

def xmlValidate(entryModelDocument):
    # test of schema validation using lxml (trial experiment, commented out for production use)
    modelXbrl = entryModelDocument.modelXbrl
    from arelle import ModelDocument
    imports = []
    importedNamespaces = set()
    for modelDocument in modelXbrl.urlDocs.values():
        if (modelDocument.type == ModelDocument.Type.SCHEMA and 
            modelDocument.targetNamespace not in importedNamespaces):
            imports.append('<xsd:import namespace="{0}" schemaLocation="{1}"/>'.format(
                modelDocument.targetNamespace, modelDocument.filepath.replace("\\","/")))
            importedNamespaces.add(modelDocument.targetNamespace)
    if entryModelDocument.xmlRootElement.hasAttributeNS(XbrlConst.xsi, "schemaLocation"):
        ns = None
        for entry in entryModelDocument.xmlRootElement.getAttributeNS(XbrlConst.xsi, "schemaLocation").split():
            if ns is None:
                ns = entry
            else:
                if ns not in importedNamespaces:
                    imports.append('<xsd:import namespace="{0}" schemaLocation="{1}"/>'.format(
                        ns, entry))
                    importedNamespaces.add(ns)
                ns = None
    schema_root = etree.XML(
        '<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema">{0}</xsd:schema>'.format(
        ''.join(imports))
        )
    import time
    startedAt = time.time()
    schema = etree.XMLSchema(schema_root)
    from arelle.Locale import format_string
    modelXbrl.modelManager.addToLog(format_string(modelXbrl.modelManager.locale, 
                                        _("schema loaded in %.2f secs"), 
                                        time.time() - startedAt))
    startedAt = time.time()
    instDoc = etree.parse(entryModelDocument.filepath)
    modelXbrl.modelManager.addToLog(format_string(modelXbrl.modelManager.locale, 
                                        _("instance parsed in %.2f secs"), 
                                        time.time() - startedAt))
    if not schema.validate(instDoc):
        for error in schema.error_log:
            modelXbrl.error(
                    str(error),
                    "err", "xmlschema:error")

def validate(modelXbrl, elt, recurse=True, attrQname=None):
    if not hasattr(elt,"xValid"):
        text = XmlUtil.text(elt)
        qnElt = qname(elt)
        modelConcept = modelXbrl.qnameConcepts.get(qnElt)
        if modelConcept is not None:
            baseXsdType = modelConcept.baseXsdType
            if len(text) == 0 and modelConcept.default is not None:
                text = modelConcept.default
        elif qnElt == XbrlConst.qnXbrldiExplicitMember: # not in DTS
            baseXsdType = "QName"
        else:
            baseXsdType = None
        if attrQname is None:
            validateValue(modelXbrl, elt, None, baseXsdType, text)
        if not hasattr(elt, "xAttributes"):
            elt.xAttributes = {}
        # validate attributes
        # find missing attributes for default values
        for attrTag, attrValue in elt.items():
            qn = qname(attrTag)
            if attrQname and attrQname != qn:
                continue
            baseXsdAttrType = None
            if modelConcept is not None:
                baseXsdAttrType = modelConcept.baseXsdAttrType(qn)
            if baseXsdAttrType is None:
                attrObject = modelXbrl.qnameAttributes.get(qn)
                if attrObject is not None:
                    baseXsdAttrType = attrObject.baseXsdType
                elif attrTag == "{http://xbrl.org/2006/xbrldi}dimension":
                    baseXsdAttrType = "QName"
            validateValue(modelXbrl, elt, attrTag, baseXsdAttrType, attrValue)
    if recurse:
        for child in elt.getchildren():
            validate(modelXbrl, child)

def validateValue(modelXbrl, elt, attrTag, baseXsdType, value):
    if baseXsdType:
        try:
            xValid = VALID
            if baseXsdType in ("decimal", "float", "double"):
                xValue = sValue = float(value)
            elif baseXsdType in ("integer",):
                xValue = sValue = int(value)
            elif baseXsdType == "boolean":
                if value in ("true", "1"):  
                    xValue = sValue = True
                elif value in ("false", "0"): 
                    xValue = sValue = False
                else: raise ValueError
            elif baseXsdType == "QName":
                xValue = qname(elt, value, castException=ValueError)
                sValue = value
            elif baseXsdType in ("normalizedString","token","language","NMTOKEN","Name","NCName","IDREF","ENTITY"):
                xValue = value.strip()
                sValue = value
            elif baseXsdType == "ID":
                xValue = value.strip()
                sValue = value
                xValid = VALID_ID
            elif baseXsdType == "dateTime":
                xValue = dateTime(value, type=DATETIME, castException=ValueError)
                sValue = value
            elif baseXsdType == "date":
                xValue = dateTime(value, type=DATE, castException=ValueError)
                sValue = value
            else:
                xValue = value
                sValue = value
        except ValueError:
            if attrTag:
                modelXbrl.error(
                    _("Element {0} attribute {1} type {2} value error: {3}").format(
                    elt.tag,
                    attrTag,
                    baseXsdType,
                    value),
                    "err", "xmlSchema:valueError")
            else:
                modelXbrl.error(
                    _("Element {0} type {1} value error: {2}").format(
                    elt.tag,
                    baseXsdType,
                    value),
                    "err", "xmlSchema:valueError")
            xValue = None
            sValue = value
            xValid = INVALID
    else:
        xValue = sValue = None
        xValid = UNKNOWN
    if attrTag:
        elt.xAttributes[attrTag] = (xValid, xValue, sValue)
    else:
        elt.xValid = xValid
        elt.xValue = xValue
        elt.sValue = sValue
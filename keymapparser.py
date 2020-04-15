# Embedded file name: /usr/lib/enigma2/python/keymapparser.py
import enigma
import xml.etree.cElementTree
from keyids import KEYIDS
from Tools.KeyBindings import addKeyBinding

class KeymapError(Exception):

    def __init__(self, message):
        self.msg = message

    def __str__(self):
        return self.msg


def getKeyId(id):
    if len(id) == 1:
        keyid = ord(id) | 32768
    elif id[0] == '\\':
        if id[1] == 'x':
            keyid = int(id[2:], 16) | 32768
        elif id[1] == 'd':
            keyid = int(id[2:]) | 32768
        else:
            raise KeymapError("[keymapparser] key id '" + str(id) + "' is neither hex nor dec")
    else:
        try:
            keyid = KEYIDS[id]
        except:
            raise KeymapError("[keymapparser] key id '" + str(id) + "' is illegal")

    return keyid


unmapDict = {}

def parseKeys(context, filename, actionmap, device, keys):
    for x in keys.findall('key'):
        get_attr = x.attrib.get
        mapto = get_attr('mapto')
        unmap = get_attr('unmap')
        id = get_attr('id')
        flags = get_attr('flags')
        if unmap is not None:
            keyid = getKeyId(id)
            actionmap.unbindPythonKey(context, keyid, unmap)
            unmapDict.update({(context, id, unmap): filename})
        else:
            keyid = getKeyId(id)
            flag_ascii_to_id = lambda x: {'m': 1,
             'b': 2,
             'r': 4,
             'l': 8}[x]
            flags = sum(map(flag_ascii_to_id, flags))
            if unmapDict.get((context, id, mapto)) in [filename, None]:
                actionmap.bindKey(filename, device, keyid, flags, context, mapto)
                addKeyBinding(filename, keyid, context, mapto, flags)

    return


def parseTrans(filename, actionmap, device, keys):
    for x in keys.findall('toggle'):
        get_attr = x.attrib.get
        toggle_key = get_attr('from')
        toggle_key = getKeyId(toggle_key)
        actionmap.bindToggle(filename, device, toggle_key)

    for x in keys.findall('key'):
        get_attr = x.attrib.get
        keyin = get_attr('from')
        keyout = get_attr('to')
        toggle = get_attr('toggle') or '0'
        keyin = getKeyId(keyin)
        keyout = getKeyId(keyout)
        toggle = int(toggle)
        actionmap.bindTranslation(filename, device, keyin, keyout, toggle)


def readKeymap(filename):
    p = enigma.eActionMap.getInstance()
    try:
        source = open(filename)
    except:
        print '[keymapparser] keymap file ' + filename + ' not found'
        return

    try:
        dom = xml.etree.cElementTree.parse(source)
    except:
        raise KeymapError('[keymapparser] keymap %s not well-formed.' % filename)

    source.close()
    keymap = dom.getroot()
    for cmap in keymap.findall('map'):
        context = cmap.attrib.get('context')
        parseKeys(context, filename, p, 'generic', cmap)
        for device in cmap.findall('device'):
            parseKeys(context, filename, p, device.attrib.get('name'), device)

    for ctrans in keymap.findall('translate'):
        for device in ctrans.findall('device'):
            parseTrans(filename, p, device.attrib.get('name'), device)


def removeKeymap(filename):
    p = enigma.eActionMap.getInstance()
    p.unbindKeyDomain(filename)
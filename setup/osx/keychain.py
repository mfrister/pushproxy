from collections import defaultdict, namedtuple
from itertools import izip
from pprint import pformat
from struct import unpack, unpack_from


class Keychain(object):
    def __init__(self, fh):
        self.fh = fh
        self.header = self.read_header()
        self.schema = self.read_schema_header(self.header.schema_offset)
        tables = self.read_tables(self.header.schema_offset, self.schema)
        schema_attributes = parse_schema_attribute_table(tables[2])
        for table in tables:
            if table.header.id in schema_attributes:
                table.apply_schema(schema_attributes[table.header.id])
        self.tables = tables

    def table_by_record_type(self, record_type):
        for table in self.tables:
            if table.header.id == record_type:
                return table

    KeychainHeader = namedtuple('KeychainHeader',
                                'magic version auth_offset schema_offset')

    def read_header(self):
        self.fh.seek(0)
        header = Keychain.KeychainHeader(*unpack('!4sIII', self.fh.read(16)))
        if header.magic != 'kych':
            raise ValueError('Wrong magic: ' + header.magic)
        return header

    SchemaHeader = namedtuple('SchemaHeader',
                              'size table_count table_offsets')

    def read_schema_header(self, offset):
        self.fh.seek(offset)
        size, table_count = unpack('!II', self.fh.read(8))
        table_offsets = unpack('!' + 'I' * table_count,
                               self.fh.read(4 * table_count))
        return Keychain.SchemaHeader(size, table_count, table_offsets)

    def read_tables(self, base_offset, schema):
        return [Table(self.fh, base_offset + offset, schema)
                for offset in schema.table_offsets]


class Table(object):
    attributes = None

    def __init__(self, fh, offset, schema):
        self.fh = fh
        self.header = self.read_table_header(offset)
        self.base_offset = offset

    def __len__(self):
        return self.header.record_numbers_count

    def __getitem__(self, key):
        offset = self.base_offset + self.header.record_offsets[key]
        return Record(self.fh, offset, self.attributes)

    def __repr__(self):
        return ('<Table size=%d, id=%d, records_count=%d, '
                    'record_numbers_count=%d>' %
                (self.header.size, self.header.id, self.header.records_count,
                    self.header.record_numbers_count))

    Header = namedtuple('TableHeader',
                        'size id records_count records_offset'
                        ' indexes_offset free_list_head'
                        ' record_numbers_count record_offsets')

    def read_table_header(self, offset):
        self.fh.seek(offset)
        fields = list(unpack('!' + 'I' * 7, self.fh.read(28)))
        record_numbers_count = fields[6]
        record_offsets = unpack('!' + 'I' * record_numbers_count,
                                self.fh.read(4 * record_numbers_count))
        fields.append(record_offsets)
        return Table.Header(*fields)

    def apply_schema(self, attributes):
        self.attributes = attributes

    def find_record_by_attribute(self, key, value):
        for record in self:
            if record.attributes[key] == value:
                return record
        raise KeyError('Record not found with %s = %s', repr(key), repr(value))


class Record(object):
    OFFSET_ATTRIBUTE_OFFSETS = 24

    def __init__(self, fh, offset, attribute_schema):
        self.base_offset = offset
        self.fh = fh
        self.header = self.read_record_header(offset)
        self.attribute_schema = attribute_schema
        self.attributes = {}

        self.read_attributes()

    def __repr__(self):
        return repr(self.header) + pformat(self.attributes)

    Header = namedtuple('RecordHeader',
                        'size number create_version record_version'
                        ' data_size semantic_information')

    def read_record_header(self, offset):
        self.fh.seek(offset)
        fields = unpack('!' + 'I' * 6, self.fh.read(6 * 4))
        return Record.Header(*fields)

    def attributes_and_data(self):
        self.fh.seek(self.base_offset + 24)
        return self.fh.read(self.header.size - 24)

    @property
    def data(self):
        begin = self.base_offset + \
                self.OFFSET_ATTRIBUTE_OFFSETS + \
                len(self.attribute_schema) * 4
        self.fh.seek(begin)

        return self.fh.read(self.header.data_size)

    # def read_record_attributes(self, count):
    #     self.fh.seek(self.base_offset + 24)  # begin of attribute offsets
    #     data = self.fh.read(count * 4)
    #     offsets = unpack_from('!' + 'I' * count, data)
    #     ends = list(offsets)
    #     del ends[0]
    #     ends.append(self.header.size)
    #     attrs = []
    #     for begin, end in zip(offsets, ends):
    #         self.fh.seek(self.base_offset + begin - 1)  # TODO why -1?
    #         attrs.append(self.fh.read(end - begin))
    #     return attrs

    def read_attribute_data(self):
        count = len(self.attribute_schema)
        self.fh.seek(self.base_offset + 24)  # begin of index offsets
        data = self.fh.read(count * 4)
        offsets = unpack_from('!' + 'I' * count, data)
        ends = list(offsets)
        del ends[0]
        ends.append(self.header.size + 1)
        attrs = []
        for begin, end in zip(offsets, ends):
            self.fh.seek(self.base_offset + begin - 1)  # TODO why -1?
            attrs.append(self.fh.read(end - begin))
        return attrs

    def read_attributes(self):
        if not self.attribute_schema:
            return
        data = self.read_attribute_data()
        for info, value in izip(self.attribute_schema, data):
            name = info.name
            self.attributes[name] = self.decode_attribute(info, value)

    def decode_attribute(self, info, value):
        funcs = {
            2: lambda value: unpack('!I', value)[0],
            6: lambda value: unpack_from(
                                '!I%is' % unpack_from('!I', value)[0],
                                value)[1],
        }
        return funcs.get(info.type, lambda x: x)(value)


Attribute2Record = namedtuple('Attribute2Record',
                              'u1 u2 u3 u4 u5 table_id u7 type u9'
                              ' name_length name u10')


def parse_attribute_record(data):
    fields = list(unpack_from('!IIIIIII4sII', data))
    if fields[3] == 61:   # no idea what this means, but in this case there
                          # are additional fields
        name_length = fields[9]
        format = '!%ds%dsI' % (name_length, (4 - (name_length % 4)) % 4)
        name, padding, u10 = unpack_from(format, data[40:])
    else:
        name, u10 = None, None
    fields += [name, u10]
    return Attribute2Record(*fields)

IndexAttributeRecord = namedtuple('Attribute2Record',
                                  'u1 u2 u3 u4 u5 u6 table_id u8 u9'
                                  ' name_length name type')


def parse_schema_attribute_record(data):
    fields = list(unpack_from('!IIIIIII4sII', data))
    if fields[3] == 61:   # no idea what this means, but in this case there
                          # are additional fields
        name_length = fields[9]
        format = '!%ds%dsI' % (name_length, (4 - (name_length % 4)) % 4)
        name, padding, u10 = unpack_from(format, data[40:])
    else:
        name, u10 = None, None
    fields += [name, u10]
    return IndexAttributeRecord(*fields)


def parse_schema_attribute_table(table):
    attributes = [parse_schema_attribute_record(
                        record.attributes_and_data())
                    for record in table]
    table_schemas = defaultdict(list)
    for attribute in attributes:
        table_schemas[attribute.table_id].append(attribute)
    return dict(table_schemas)

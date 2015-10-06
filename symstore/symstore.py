import os
import shutil
import pdbparse
import pefile
from os import path
from datetime import datetime


ADMIN_DIR = "000Admin"
LAST_ID_FILE = path.join(ADMIN_DIR, "lastid.txt")
HISTORY_FILE = path.join(ADMIN_DIR, "history.txt")
SERVER_FILE = path.join(ADMIN_DIR, "server.txt")
PINGME_FILE = "pingme.txt"

PDB_IMAGE, PE_IMAGE = range(2)

EXT_TYPES = dict(pdb=PDB_IMAGE,
                 exe=PE_IMAGE,
                 dll=PE_IMAGE)


def _pdb_hash(filename):
    pdb = pdbparse.parse(filename, fast_load=True)

    pdb.STREAM_PDB.load()
    guid = pdb.STREAM_PDB.GUID
    guid_str = "%.8X%.4X%.4X%s" % (guid.Data1, guid.Data2, guid.Data3,
                                   guid.Data4.encode("hex").upper())

    return "%s%s" % (guid_str, pdb.STREAM_PDB.Age)


def _pe_hash(file):
    pe = pefile.PE(file, fast_load=True)

    return "%X%X" % (pe.FILE_HEADER.TimeDateStamp,
                     pe.OPTIONAL_HEADER.SizeOfImage)


def _image_type(file):
    file_ext = path.splitext(file)[1][1:].lower()
    # TODO handle cases of unknown file extensions
    return EXT_TYPES[file_ext]


def _file_hash(file):

    image_type = _image_type(file)

    if image_type == PDB_IMAGE:
        return _pdb_hash(file)

    assert image_type == PE_IMAGE
    return _pe_hash(file)


def _new_or_empty(filename):
    if not path.isfile(filename):
        return True

    return os.stat(filename).st_size == 0


def _append_line(filename, line):
    with open(filename, "a") as f:
        f.write("%s" % line)


class SymbolsStore:
    def __init__(self, store_path):
        self._path = store_path

    @property
    def _admin_dir(self):
        return path.join(self._path, ADMIN_DIR)

    @property
    def _last_id_file(self):
        return path.join(self._path, LAST_ID_FILE)

    @property
    def _history_file(self):
        return path.join(self._path, HISTORY_FILE)

    @property
    def _server_file(self):
        return path.join(self._path, SERVER_FILE)

    @property
    def _pingme_file(self):
        return path.join(self._path, PINGME_FILE)

    def create_dirs(self):
        if not path.isdir(self._path):
            os.mkdir(self._path)
            # TODO handle mkdir errors

        admin_dir = self._admin_dir
        if not path.isdir(admin_dir):
            os.mkdir(admin_dir)
            # TODO handle mkdir errors

    def _next_trans_id(self):
        last_id_file = self._last_id_file

        if not path.isfile(last_id_file):
            next_id = 1
        else:
            cur_id = open(last_id_file, "r").read()
            # TODO handle open and read errors
            next_id = int(cur_id) + 1
            # TODO handle parse errors

        return "%.010d" % next_id

    def _store_file(self, file):
        file_dir = path.join(path.basename(file), _file_hash(file))
        dest_dir = path.join(self._path, file_dir)

        os.makedirs(dest_dir)
        shutil.copy(file, dest_dir)

        return file_dir

    def _write_transaction_file(self, transaction_id, added_entries):
        transaction_filename = path.join(self._admin_dir, transaction_id)
        with open(transaction_filename, "w") as transfile:
            for pdb_dir, file in added_entries:
                pdb_dir = pdb_dir.replace("/", "\\")
                file = path.abspath(file)
                transfile.write("\"%s\",\"%s\"\n" % (pdb_dir, file))
        # TODO handle file write errors

    def _write_history(self, start_time, transaction_id, product, version):
        date_stamp = start_time.strftime("%d/%m/%y")
        time_stamp = start_time.strftime("%H:%M:%S")

        log_line = """%s,add,file,%s,%s,"%s","%s","",""" % \
                   (transaction_id, date_stamp, time_stamp, product, version)

        _append_line(self._history_file, log_line + "\n")

        line_break = "" if _new_or_empty(self._server_file) else "\n"
        _append_line(self._server_file, line_break + log_line)

    def _write_transaction_id(self, trans_id):
        with open(self._last_id_file, "w") as id_file:
            id_file.write(trans_id)

    def _touch_pingme(self):
        pingme_path = self._pingme_file

        if not path.isfile(pingme_path):
            open(pingme_path, "a")
            return

        os.utime(pingme_path, None)

    def add(self, files, product, version):
        trans_start_time = datetime.now()
        self.create_dirs()
        trans_id = self._next_trans_id()

        added_dirs = []

        for file in files:
            added_dirs.append(self._store_file(file))

        self._write_transaction_file(trans_id, zip(added_dirs, files))
        self._write_history(trans_start_time, trans_id, product, version)
        self._write_transaction_id(trans_id)
        self._touch_pingme()
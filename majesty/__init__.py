import struct
import io
from PIL import Image, ImageDraw
from typing import TYPE_CHECKING, NamedTuple, List
StrOrBytesPath = None
if TYPE_CHECKING:
    from _typeshed import StrOrBytesPath


class Type(NamedTuple):
    name: bytes
    offset: int


class Entry(NamedTuple):
    id: int
    name: bytes
    offset: int
    size: int


class CamFile:
    file_name: StrOrBytesPath
    types: List[Type]
    entries_per_type: List[List[Entry]]

    def __init__(self):
        self.file_name = ''
        self.types = []
        self.entries_per_type = []

    def get_index_of(self, type_name: bytes) -> int:
        for i, type in enumerate(self.types):
            if type_name in type.name:
                return i

        return -1

    def list_image_entries(self) -> List[Entry]:
        index_of_til = self.get_index_of(b'TIL')
        return self.entries_per_type[index_of_til]

    def get_image(self, index: int) -> Image:
        with open(self.file_name, 'rb') as cam_file:
            index_of_til = self.get_index_of(b'TIL')
            if index < 0 or index > len(self.entries_per_type[index_of_til]):
                return None

            tile_data = None
            entry = self.entries_per_type[index_of_til][index]
            cam_file.seek(entry.offset)
            tile_data = cam_file.read(entry.size)

            # Resource header
            img_type, = struct.unpack('H', tile_data[:2])
            height, width, _ = struct.unpack('HHH', tile_data[2:8])
            _, _, _, _, _ = struct.unpack('HHIIH', tile_data[8:22])
            palette_index, = struct.unpack('I', tile_data[22:26])

            # Get the palette
            index_of_splt = self.get_index_of(b'SPLT')
            palette = self.entries_per_type[index_of_splt][palette_index]
            cam_file.seek(palette.offset)
            palette_data = cam_file.read(palette.size)

            return create_image(tile_data, palette_data)


def read_cam(file_name: StrOrBytesPath) -> CamFile:
    cam = CamFile()
    with open(file_name, 'rb') as cam_file:
        cam.file_name = file_name
        _, _, _, type_count, content_offset = struct.unpack('8sHHII', cam_file.read(20))

        for i in range(type_count):
            type_name, offset = struct.unpack('4sI', cam_file.read(8))
            cam.types.append(Type(type_name, offset))

        # Content is offset after the type descriptions
        content_offset = content_offset + cam_file.tell()

        # A list of entries for each type
        for i in range(type_count):
            number_of_entries, _ = struct.unpack('II', cam_file.read(8))

            entry = []
            for _ in range(number_of_entries):
                ident, name, offset, size = struct.unpack('I16sII', cam_file.read(28))
                entry.append(Entry(ident, name, offset, size))

            cam.entries_per_type.append(entry)

        # Should be as many arrays as types
        assert(len(cam.entries_per_type) == len(cam.types))

        return cam


def create_image(tile_data: bytes, palette_data: bytes, draw_shadows: bool = True) -> Image:
    colours = []
    with io.BytesIO(palette_data) as palette_file:
        palette_file.read(8)  # dunno

        while len(colour_data := palette_file.read(3)) > 0:
            colour = struct.unpack('BBB', colour_data)
            palette_file.read(1)  # zero
            colours.append(colour)

    with io.BytesIO(tile_data) as file:
        # Resource header
        img_type, = struct.unpack('H', file.read(2))
        height, width, _ = struct.unpack('HHH', file.read(6))
        _, _, _, _, _ = struct.unpack('HHIIH', file.read(14))
        palette_index, = struct.unpack('I', file.read(4))

        for i in range(height):
            # NOTE: The data stored here is likely a 4-byte signed integer
            file.read(4)

        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        for i in range(width):
            for j in range(height):
                draw.point((i, j), fill=colours[255])

        row = 0
        while header := file.read(4):
            position, pixel_number, pixel_type = struct.unpack('HBB', header)
            if pixel_type == 128 and pixel_number == 0:
                row += 1
                continue

            if pixel_type >= 128:
                number_of_pixels = (pixel_type - 128) * 256 + pixel_number
            else:
                number_of_pixels = pixel_type * 256 + pixel_number

            col = 0
            for b in file.read(number_of_pixels):
                if b > 247 and draw_shadows is False:
                    continue

                x_coord = position - number_of_pixels + col
                draw.point((x_coord, row), fill=colours[b])
                col += 1

            if pixel_type >= 128:
                row += 1

    return img

# Majesty CAM Reader

## Example
```py
import majesty
import random

cam_file = majesty.read_cam("maindata.cam")
images = cam_file.list_image_entries()
tax_collectors = [entry for entry in images if b'Tax Collector' in entry.name]
random_entry = random.choice(tax_collectors)
random_image = cam_file.get_image(random_entry.id)
random_image.show()
```

## Credits
* Many thanks to TheRancid and his work on [Majesty Library](https://github.com/TheRancid/MajestyLibrary)
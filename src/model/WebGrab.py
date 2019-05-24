__author__ = 'eliagenini'

class WebGrab:
    def __init__(self, id, site, site_id, name, same_as=None, offset=None):
        self.id = id
        self.site = site
        self.site_id = site_id
        self.name = name
        self.same_as = same_as
        self.offset = offset
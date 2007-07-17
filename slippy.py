#!/usr/bin/python
# -*- coding:utf8 -*-

import sys
import types
import cairo
import rsvg
import pygtk
pygtk.require('2.0')
import gtk
import gtk.gdk
import pango
import pangocairo
import gobject

class ViewerGTK(gtk.Widget):

	def do_realize(self):
		self.set_flags(self.flags() | gtk.REALIZED)

		self.window = gtk.gdk.Window(
			self.get_parent_window(),
			width=self.allocation.width,
			height=self.allocation.height,
			window_type=gtk.gdk.WINDOW_CHILD,
			wclass=gtk.gdk.INPUT_OUTPUT,
			event_mask=self.get_events() | gtk.gdk.EXPOSURE_MASK)

		self.window.set_user_data(self)

		self.style.attach(self.window)

		self.style.set_background(self.window, gtk.STATE_NORMAL)
		self.window.move_resize(*self.allocation)

	def do_unrealize(self):
		self.window.destroy()

	def do_expose_event(self, event):
		cr = pangocairo.CairoContext (self.window.cairo_create())

		cr.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
		cr.clip()

		renderer = Renderer (viewer=self, theme=self.theme, cr=cr, width=self.allocation.width, height=self.allocation.height)

		self.slide.show_page (self, renderer, self.step)

		return False
	
	def go_forward_full(self):
		if self.slide_no + 1 < len (self.slides):
			self.slide_no += 1
			self.slide = Slide (self.slides[self.slide_no])
			self.step = 0
			self.queue_draw()

	def go_forward(self):
		if self.step + 1 < len (self.slide):
			self.step += 1
			self.queue_draw()
		else:
			self.go_forward_full ()

	def go_backward_full(self):
		if self.slide_no > 0:
			self.slide_no -= 1
			self.slide = Slide (self.slides[self.slide_no])
			self.step = 0
			self.queue_draw()

	def go_backward(self):
		if self.step > 0:
			self.step -= 1
			self.queue_draw()
		else:
			self.go_backward_full ()
			self.step = len (self.slide) - 1
			self.queue_draw()

	def key_press_event(self, widget, event):
		if event.string in [' ', '\r'] or event.keyval in [gtk.keysyms.Right, gtk.keysyms.Down]:
			self.go_forward()
		elif event.keyval in [gtk.keysyms.Page_Down]:
			self.go_forward_full()
		elif event.keyval == gtk.keysyms.BackSpace or event.keyval in [gtk.keysyms.Left, gtk.keysyms.Up]:
			self.go_backward()
		elif event.keyval in [gtk.keysyms.Page_Up]:
			self.go_backward_full()
		elif event.string == 'q':# or event.keyval == gtk.keysyms.Escape:
			gtk.main_quit()

	def run (self, theme, slides):
		self.cache = True
		self.cached = False

		self.theme = theme
		self.slides = slides

		window = gtk.Window()
		window.add(self)
		window.connect("destroy", gtk.main_quit)
		window.connect("key-press-event", self.key_press_event)
		window.set_default_size (800, 600)
		window.set_default_size (800, 600)
		window.show_all()

		self.slide_no = 0
		self.step = 0
		self.slide = Slide (self.slides[self.slide_no])

		gtk.main()


class ViewerPDF:

	def __init__ (self, filename):
		self.width, self.height = 8.5 * 4/3 * 72, 8.5 * 72
		self.surface = cairo.PDFSurface (filename, self.width, self.height)

	def run (self, theme, slides):
		self.cache = False
		cr = pangocairo.CairoContext (cairo.Context (self.surface))
		renderer = Renderer (None, theme, cr, self.width, self.height)
		for slide in slides:
			slide = Slide (slide)
			for step in range (len (slide)):
				slide.show_page (self, renderer, step)


class Slide:

	def __init__ (self, slide):
		renderer = Renderer ()
		self.slide, self.who = slide
		self.texts = [x for x in self.get_items (renderer)]
		self.extents = renderer.extents
		self.text = ''.join (self.texts)
	
	def get_items (self, renderer):
		items = self.slide
		if isinstance (items, types.FunctionType):
			items = items(renderer)
		if items == None:
			items = ("",)
		if isinstance (items, str):
			items = (items,)
		items = [item + " "*int(item == "" or item == None) for item in items]
		return items

	def __len__ (self):
		return len (self.texts)
	
	def show_page (self, viewer, renderer, pageno):
		cr = renderer.cr
		cr.save ()
		if viewer.cache and viewer.cached and (renderer.width, renderer.height) == viewer.cached_size:
			x, y, w, h = viewer.cached_canvas_size
			renderer.set_source_surface (viewer.cached_surface)
			renderer.paint ()
		elif viewer.cache:
			x, y, w, h = renderer.theme.prepare_page (renderer)
			viewer.cached_size = (renderer.width, renderer.height)
			viewer.cached_canvas_size = [x, y, w, h]
			surface = renderer.get_target().create_similar (cairo.CONTENT_COLOR_ALPHA, int(viewer.cached_size[0]), int(viewer.cached_size[1]))
			ncr = cairo.Context (surface)
			ncr.set_source_surface (renderer.get_target (), 0, 0)
			ncr.paint ()
			viewer.cached_surface = surface
			viewer.cached = True
		else:
			x, y, w, h = renderer.theme.prepare_page (renderer)

		cr.translate (x, y)

		# normalize canvas size
		cr.scale (w / 800., h / 600.)
		w, h = 800., 600.
		renderer.w, renderer.h = w,h
		cr.move_to (0, 0)

		layout = renderer.create_layout (self.text)
		layout.set_alignment (pango.ALIGN_CENTER)
		lw, lh = renderer.fit_layout (layout, w, h)

		ext = self.extents
		if self.text != " ":
			ext = extents_union (ext, [(w - lw) * .5, (h - lh) * .5, lw, lh])
		ext = extents_intersect (ext, [0, 0, w, h])
		#ex, ey, ew, eh = self.extents
		#ex, ey = cr.device_to_user (ex, ey)
		#ew, eh = cr.device_to_user_distance (ew, eh)
		renderer.theme.draw_bubble (renderer, who=self.who, *ext)

		text = ""
		i = 0;
		for page in self.get_items (renderer):
			text += page
			if i == pageno:
				break;
			i += 1

		layout.set_width (lw * pango.SCALE)
		layout.set_markup (text)
		cr.move_to ((w - lw) * .5, (h - lh) * .5)
		cr.show_layout (layout)
		cr.restore ()

		cr.show_page()
		
def extents_union (ex1, ex2):
	
	if not ex1:
		return ex2
	else:
		x1 = min (ex1[0], ex2[0])
		y1 = min (ex1[1], ex2[1])
		x2 = max (ex1[0] + ex1[2], ex2[0] + ex2[2])
		y2 = max (ex1[1] + ex1[3], ex2[1] + ex2[3])
		return [x1, y1, x2 - x1, y2 - y1]

def extents_intersect (ex1, ex2):
	
	if not ex1:
		return ex2
	else:
		x1 = max (ex1[0], ex2[0])
		y1 = max (ex1[1], ex2[1])
		x2 = min (ex1[0] + ex1[2], ex2[0] + ex2[2])
		y2 = min (ex1[1] + ex1[3], ex2[1] + ex2[3])
		return [x1, y1, x2 - x1, y2 - y1]

class Renderer:
	
	def __init__ (self, viewer=None, theme=None, cr=None, width=0, height=0):
		if not theme:
			class NullTheme:
				def prepare_page (renderer):
					return 0, 0, renderer.width, renderer.height
				def draw_bubble (renderer):
					pass
			theme = NullTheme ()
		if not cr:
			cr = pangocairo.CairoContext (cairo.Context (cairo.ImageSurface (0, 0, 0)))
		if not width:
			width = 8
		if not height:
			height = 6

		self.viewer = viewer
		self.cr = cr
		self.theme = theme
		self.width, self.height = float (width), float (height)
		self.extents = None

	def __getattr__ (self, arg):
		return eval ("self.cr." + arg)
	
	def allocate (self, x, y, w, h):
		x, y = self.cr.user_to_device (x, y)
		w, h = self.cr.user_to_device_distance (w, h)
		self.extents = extents_union (self.extents, [x, y, w, h])

	def create_layout (self, text, markup=True):

		cr = self.cr
		
		layout = cr.create_layout ()
		font_options = cairo.FontOptions ()
		font_options.set_hint_metrics (cairo.HINT_METRICS_OFF)
		pangocairo.context_set_font_options (layout.get_context (), font_options)

		if markup:
			layout.set_markup (text)
		else:
			layout.set_text (text)

		return layout

	def fit_layout (self, layout, width, height):

		width *= pango.SCALE
		height *= pango.SCALE

		cr = self.cr

		cr.update_layout (layout)
		desc = layout.get_font_description ()
		if not desc:
			desc = pango.FontDescription("Sans")
		s = int (max (height * 5., width / 50.))
		if s:
			desc.set_size (s)
		elif desc.get_size () == 0:
			desc.set_size (36 * pango.SCALE)
		layout.set_font_description (desc)

		if s:
			w,h = layout.get_size ()
			if width > 0:
				size = float (width) / w
				if height > 0:
					size = min (size, float (height) / h)
			elif height > 0:
				size = float (height) / h
			else:
				size = 1

			desc.set_size (int (s * size)) 

		layout.set_font_description (desc)

		return layout.get_pixel_size ()

	def put_text (self, text, width=0, height=0, halign=0, valign=0, markup=True, desc=None):
		layout = self.create_layout (text, markup=markup)
		if desc:
			layout.set_font_description (pango.FontDescription (desc))
		if halign < 0:
			layout.set_alignment (pango.ALIGN_RIGHT)
		elif halign > 0:
			layout.set_alignment (pango.ALIGN_LEFT)
		else:
			layout.set_alignment (pango.ALIGN_CENTER)

		width, height = self.fit_layout (layout, width, height)
		self.cr.rel_move_to ((halign - 1) * width / 2., (valign - 1) * height / 2.)
		x, y = self.cr.get_current_point ()
		self.cr.show_layout (layout)
		self.allocate (x, y, width, height)
		return width, height

	def put_image (self, filename, width=0, height=0, halign=0, valign=0):

		global pixcache
		pix, w, h = pixcache.get (filename, (None, 0, 0))

		svg = filename.endswith (".svg")

		if not pix:
			if svg:
				pix = rsvg.Handle (filename)
				w, h = pix.get_dimension_data()[2:4]
			else:
				pix = gtk.gdk.pixbuf_new_from_file (filename)
				w, h = pix.get_width(), pix.get_height()
				surface = self.get_target().create_similar (cairo.CONTENT_COLOR_ALPHA, w, h)
				gcr = gtk.gdk.CairoContext (cairo.Context (surface))
				gcr.set_source_pixbuf (pix, 0, 0)
				gcr.paint ()
				pix = surface

		pixcache[filename] = (pix, w, h)

		cr = self.cr
		x, y = cr.get_current_point ()
		r = 0
		width, height = float (width), float (height)
		if width or height:
			if width:
				r = width / w
				if height:
					r = min (r, height / h)
			elif height:
				r = height / h
		cr.save ()
		cr.translate (x, y)
		if r:
			cr.scale (r, r)
		cr.translate ((halign - 1) * w / 2., (valign - 1) * h / 2.)
		cr.move_to (0, 0)

		if svg:
			pix.render_cairo (cr)
		else:
			cr.set_source_surface (pix, 0, 0)
			cr.paint ()
		self.allocate (0, 0, w * r, h * r)
		cr.restore ()
		return w * r, h * r

pixcache = {}
gobject.type_register(ViewerGTK)


def main():
	import slides
	all_slides = slides.slides

	if len(sys.argv) == 2:
		viewer = ViewerPDF (sys.argv[1])
	else:
		viewer = ViewerGTK ()

	import theme

	viewer.run (theme, all_slides)

if __name__ == "__main__":
	main()

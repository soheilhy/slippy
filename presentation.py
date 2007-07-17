#!/usr/bin/python
# -*- coding:utf8 -*-

import sys
import types
import cairo
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

		renderer = Renderer (theme=self.theme, cr=cr, width=self.allocation.width, height=self.allocation.height)

		self.slide.show_page (renderer, self.step)

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
		self.theme = theme
		self.slides = slides

		window = gtk.Window()
		window.add(self)
		window.connect("destroy", gtk.main_quit)
		window.connect("key-press-event", self.key_press_event)
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
		cr = pangocairo.CairoContext (cairo.Context (self.surface))
		renderer = Renderer (theme, cr, self.width, self.height)
		for slide in slides:
			slide = Slide (slide)
			for step in range (len (slide)):
				slide.show_page (renderer, step)


class Slide:

	def __init__ (self, slide):
		self.slide = slide
		self.texts = [x for x in self.get_items (Renderer ())]
		self.text = ''.join (self.texts)
	
	def get_items (self, renderer):
		items = self.slide
		if isinstance (items, types.FunctionType):
			items = items(renderer)
		if items == None or items == "":
			items = (" ",)
		if isinstance (items, str):
			items = (items,)
		return items

	def __len__ (self):
		return len (self.texts)
	
	def show_page (self, renderer, pageno):
		cr = renderer.cr
		cr.save ()
		x, y, w, h = renderer.theme.prepare_page (renderer)
		cr.translate (x, y)
		cr.rectangle (0, 0, w, h)
		cr.clip ()
		cr.scale (w / 800., h / 600.)
		w, h = 800., 600.
		cr.move_to (0, 0)

		layout = renderer.create_layout (self.text)
		lw, lh = renderer.fit_layout (layout, w, h)
		text = ""
		i = 0;
		for page in self.get_items (renderer):
			text += page
			if i == pageno:
				break;
			i += 1
		layout.set_markup (text)
		cr.move_to ((w - lw) * .5, (h - lh) * .5)
		cr.show_layout (layout)
		cr.restore ()

		cr.show_page()
		

class Renderer():
	
	def __init__ (self, theme=None, cr=None, width=0, height=0):
		if not theme:
			class NullTheme:
				def prepare_page (renderer):
					return 0, 0, renderer.width, renderer.height
			theme = NullTheme ()
		if not cr:
			cr = cairo.Context (cairo.ImageSurface (0, 0, 0))
		if not width:
			width = 8
		if not height:
			height = 6

		self.cr = cr
		self.theme = theme
		self.width, self.height = float (width), float (height)

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
		desc = pango.FontDescription("Sans")
		s = int (max (height * 5., width / 50.))
		desc.set_size (s)
		layout.set_font_description (desc)
		w,h = layout.get_size ()
		if width > 0:
			size = float (width) / w
			if height > 0:
				size = min (size, float (height) / h)
		else:
			size = float (height) / h

		desc.set_size (int (s * size)) 
		layout.set_font_description (desc)

		return layout.get_pixel_size ()

	def put_text (self, text, width=0, height=0, halign=0, valign=0, markup=True):
		layout = self.create_layout (text, markup=markup)
		width, height = self.fit_layout (layout, width, height)
		self.cr.rel_move_to ((halign - 1) * width / 2., (valign - 1) * height / 2.)
		self.cr.show_layout (layout)
		return width, height

	def put_image (self, filename, width=0, height=0, halign=0, valign=0):
		pix = gtk.gdk.pixbuf_new_from_file (filename)
		gcr = gtk.gdk.CairoContext (self.cr)
		x, y = gcr.get_current_point ()
		r = 0
		width, height = float (width), float (height)
		if width or height:
			if width:
				r = width / pix.get_width ()
				if height:
					r = min (r, height / pix.get_height ())
			elif height:
				r = height / pix.get_height ()
		width, height = pix.get_width (), pix.get_height ()
		gcr.save ()
		gcr.translate (x, y)
		if r:
			gcr.scale (r, r)
		gcr.set_source_pixbuf (pix, (halign - 1) * width / 2., (valign - 1) * height / 2.)
		gcr.paint ()
		gcr.restore ()

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
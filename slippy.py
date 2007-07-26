#!/usr/bin/python
# -*- coding:utf8 -*-

# Written by Behdad Esfahbod, 2007
# Not copyrighted, in public domain.

import types
import cairo
import rsvg
import pygtk
pygtk.require('2.0')
import gobject
import pango
import pangocairo
import gtk
import gtk.gdk

class Viewer:
	def _should_cache_background (self):
		return False

	def is_slideshow (self):
		return False

	def run (self, slides, theme=None):
		pass

class ViewerGTK (Viewer):
	
	def __init__(self, fullscreen=False, repeat=False, slideshow=False, delay=5., width=800, height=600):
		self.__fullscreen = fullscreen
		self.__repeat = repeat
		self.__slideshow = slideshow
		self.__delay = delay
		self.__cache = True

		window = gtk.Window()
		screen = window.get_screen()
		colormap = screen.get_rgba_colormap()
		# TODO: we should check screen/window.is_composited() here
		# too, but those return False all the time for me
		if colormap:
			window.set_colormap (colormap)
			# caching background only speeds up rendering for
			# color-only surfaces
			self.__cache = False
		window.set_app_paintable(True)
		window.connect("destroy", gtk.main_quit)
		window.connect("key-press-event", self.__key_press_event)
		window.connect("expose-event", self.__expose_event)
		window.set_default_size (width, height)
		self.window = window

	def get_slide(self):
		if not self.slide:
			self.slide = Slide (self.slides[self.slide_no])
		return self.slide

	def is_fullscreen(self):
		return self.__fullscreen

	def fullscreen(self):
		print "fullscreen"
		#self.window.maximize ()
		self.window.fullscreen ()
		self.__fullscreen = True

	def unfullscreen(self):
		print "unfullscreen"
		self.window.unfullscreen ()
		#self.window.unmaximize ()
		self.__fullscreen = False

	def toggle_fullscreen(self):
		if self.__fullscreen:
			self.unfullscreen()
		else:
			self.fullscreen()

	def is_repeat(self):
		return self.__repeat

	def toggle_repeat(self):
		self.__repeat = not self.__repeat

	def is_slideshow (self):
		return self.__slideshow

	def __remove_slideshow_timeout(self):
		if self.timeout_source:
			gobject.source_remove (self.timeout_source)
			self.timeout_source = None;

	def start_slideshow(self):
		if not self.__slideshow:
			print "starting slideshow with delay %gs" % self.__delay

		self.__remove_slideshow_timeout ()
		self.__slideshow = True
		# we want to wait "delay" seconds after expose is done, that's
		# why we don't use a simple recurring timeout, but add an idle
		# callback, in the idle set a timeout, in the timeout set the
		# idle again, repeat...
		def idle_callback():
			def timeout_callback():
				self.timeout_source = gobject.idle_add (idle_callback)
				self.go_forward ()
				return False
			self.timeout_source = gobject.timeout_add (int (self.__delay * 1000), timeout_callback)
			return False
		self.timeout_source = gobject.idle_add (idle_callback)

	def stop_slideshow(self):
		if self.__slideshow:
			print "stopping slideshow"

		self.__slideshow = False
		self.__remove_slideshow_timeout ()

	def toggle_slideshow(self):
		if self.__slideshow:
			self.stop_slideshow()
		else:
			self.start_slideshow()
	
	def get_slideshow_delay(self):
		return self.__delay

	def set_slideshow_delay(self, delay):
		print "setting slideshow delay to %gs" % delay
		self.__delay = delay
		self.__tick ()

	def __tick(self):
		if self.__slideshow:
			self.start_slideshow()

	def __queue_draw(self):
		self.window.queue_draw()

	def _should_cache_background (self):
		return self.__cache

	def go_forward_full(self):
		if self.slide_no + 1 < len (self.slides):
			self.slide_no += 1
			self.slide = None
			self.step = 0
			self.__queue_draw()
		elif self.is_repeat():
			self.slide_no = 0
			self.slide = None
			self.step = 0
			self.__queue_draw()
		else:
			self.stop_slideshow()

	def go_forward(self):
		if self.step + 1 < len (self.get_slide ()):
			self.step += 1
			self.__queue_draw()
		else:
			self.go_forward_full ()

	def go_backward_full(self):
		if self.slide_no > 0:
			self.slide_no -= 1
			self.slide = None
			self.step = 0
			self.__queue_draw()

	def go_backward(self):
		if self.step > 0:
			self.step -= 1
			self.__queue_draw()
		else:
			self.go_backward_full ()
			self.step = len (self.get_slide ()) - 1
			self.__queue_draw()

	def __key_press_event(self, widget, event):
		if event.string in [' ', '\r'] or event.keyval in [gtk.keysyms.Right, gtk.keysyms.Down]:
			self.__tick ()
			self.go_forward()
		elif event.keyval in [gtk.keysyms.Page_Down]:
			self.__tick ()
			self.go_forward_full()
		elif event.keyval == gtk.keysyms.BackSpace or event.keyval in [gtk.keysyms.Left, gtk.keysyms.Up]:
			self.__tick ()
			self.go_backward()
		elif event.keyval in [gtk.keysyms.Page_Up]:
			self.__tick ()
			self.go_backward_full()
		elif event.string == 'q':# or event.keyval == gtk.keysyms.Escape:
			gtk.main_quit()
		elif event.string == 'f':
			self.toggle_fullscreen ()
		elif event.string == 's':
			self.toggle_slideshow ()
		elif event.string == 'a':
			self.set_slideshow_delay (self.get_slideshow_delay () / 1.2)
		elif event.string == 'z':
			self.set_slideshow_delay (self.get_slideshow_delay () * 1.2)
		elif event.string == 'r':
			self.toggle_repeat ()

	def __expose_event(self, widget, event):
		cr = pangocairo.CairoContext (widget.window.cairo_create())
		cr.rectangle(event.area.x, event.area.y, event.area.width, event.area.height)
		cr.clip()

		renderer = Renderer (viewer=self, cr=cr, width=widget.allocation.width, height=widget.allocation.height)

		self.get_slide().show_page (renderer, self.step, theme=self.theme)

		return False


	def run (self, slides, theme=None):

		self.slides = slides
		self.theme = theme
		self.timeout_source = None

		self.window.show()
		self.cached_slide = None
		self.slide_no = 0
		self.step = 0
		self.slide = None

		if self.is_fullscreen():
			self.fullscreen()
		if self.is_slideshow():
			self.start_slideshow()

		gtk.main()


class ViewerFile (Viewer):

	def __init__ (self, filename, width=8.5*4/3*72, height=8.5*72):
		self.width, self.height = width, height
		if filename.endswith (".pdf"):
			Klass = cairo.PDFSurface
		elif filename.endswith (".ps"):
			Klass = cairo.PSSurface
		elif filename.endswith (".svg"):
			Klass = cairo.SVGSurface
		else:
			raise Exception ("Donno how to save as %s" % filename)

		self.surface = Klass (filename, self.width, self.height)

	def run (self, slides, theme=None):
		for slide in slides:
			title = slide[0]
			if isinstance (title, types.FunctionType):
				title = title.__name__
			print "Slide", title.replace ('\n', ' ')
			slide = Slide (slide)
			for step in range (len (slide)):
				cr = pangocairo.CairoContext (cairo.Context (self.surface))
				renderer = Renderer (self, cr, self.width, self.height)
				slide.show_page (renderer, step, theme=theme)
				print "Step", step


class Slide:

	def __init__ (self, slide):
		self.slide, self.data, self.width, self.height = slide

		self.width, self.height = float (self.width), float (self.height)

		renderer = Renderer ()
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
		return items

	def __len__ (self):
		return len (self.texts)
	
	def show_page (self, renderer, pageno, theme=None):
		class NullTheme:
			def prepare_page (self, renderer):
				return 0, 0, renderer.width, renderer.height
			def draw_bubble (self, renderer, *args, **kargs):
				pass
		if not theme:
			theme = NullTheme()
		viewer = renderer.viewer
			
		cr = renderer.cr
		cr.save ()
		if viewer and viewer._should_cache_background() and viewer.cached_slide and (renderer.width, renderer.height) == viewer.cached_slide_size:
			x, y, w, h = viewer.cached_slide_canvas_size
			renderer.save ()
			renderer.set_source_surface (viewer.cached_slide_surface)
			renderer.set_operator (cairo.OPERATOR_SOURCE)
			renderer.paint ()
			renderer.restore ()
		else:
		
			#renderer.save ()
			#renderer.set_operator (cairo.OPERATOR_CLEAR)
			#renderer.paint ()
			#renderer.restore ()
			#renderer.set_source_rgb (.5, .5, .5)
			x, y, w, h = theme.prepare_page (renderer)

			if viewer and viewer._should_cache_background():
				viewer.cached_slide_size = (renderer.width, renderer.height)
				viewer.cached_slide_canvas_size = [x, y, w, h]
				surface = renderer.get_target().create_similar (cairo.CONTENT_COLOR, int(viewer.cached_slide_size[0]), int(viewer.cached_slide_size[1]))
				ncr = cairo.Context (surface)
				ncr.save ()
				ncr.set_source_surface (renderer.get_target (), 0, 0)
				ncr.set_operator (cairo.OPERATOR_SOURCE)
				ncr.paint ()
				ncr.restore ()
				viewer.cached_slide_surface = surface
				viewer.cached_slide = True

		cr.translate (x, y)

		# normalize canvas size
		cr.scale (w / self.width, h / self.height)
		w, h = self.width, self.height
		renderer.w, renderer.h = w,h
		cr.move_to (0, 0)

		layout = renderer.create_layout (self.text)
		if self.text.find ('\t') == -1:
			layout.set_alignment (pango.ALIGN_CENTER)
		lw, lh = renderer.fit_layout (layout, w, h)

		ext = self.extents
		#if ext:
		#	ex, ey, ew, eh = ext
		#	ex, ey = cr.device_to_user (ex, ey)
		#	ew, eh = cr.device_to_user_distance (ew, eh)
		#	ext = [ex, ey, ew, eh]
		if self.text:
			ext = _extents_union (ext, [(w - lw) * .5, (h - lh) * .5, lw, lh])
		ext = _extents_intersect (ext, [0, 0, w, h])
		theme.draw_bubble (renderer, data=self.data, *ext)

		text = ""
		i = 0;
		for page in self.get_items (renderer):
			text += page
			if i == pageno:
				break;
			i += 1

		layout.set_width (int (1.001 * lw * pango.SCALE))
		layout.set_markup (_remove_empty_lines (text))
		cr.move_to ((w - lw) * .5, (h - lh) * .5)
		cr.show_layout (layout)
		cr.restore ()

		cr.show_page()
		
def _extents_union (ex1, ex2):
	
	if not ex1:
		return ex2
	else:
		x1 = min (ex1[0], ex2[0])
		y1 = min (ex1[1], ex2[1])
		x2 = max (ex1[0] + ex1[2], ex2[0] + ex2[2])
		y2 = max (ex1[1] + ex1[3], ex2[1] + ex2[3])
		return [x1, y1, x2 - x1, y2 - y1]

def _extents_intersect (ex1, ex2):
	
	if not ex1:
		return ex2
	else:
		x1 = max (ex1[0], ex2[0])
		y1 = max (ex1[1], ex2[1])
		x2 = min (ex1[0] + ex1[2], ex2[0] + ex2[2])
		y2 = min (ex1[1] + ex1[3], ex2[1] + ex2[3])
		return [x1, y1, x2 - x1, y2 - y1]

def _remove_empty_lines (text):
	"""replace empty lines with lines of a single space.  this works
	around a pango bug with wrong computation of line height for empty
	lines under cairo scales"""
	text = text.replace ("\n\n", "\n \n")
	if text.endswith ("\n"):
		text += " "
	return text


class Renderer:
	
	def __init__ (self, viewer=None, cr=None, width=0, height=0):
		if not cr:
			cr = pangocairo.CairoContext (cairo.Context (cairo.ImageSurface (0, 0, 0)))
		if not width:
			width = 8
		if not height:
			height = 6

		self.viewer = viewer
		self.cr = cr
		self.width, self.height = float (width), float (height)
		self.extents = None

	def __getattr__ (self, arg):
		return eval ("self.cr." + arg)
	
	def allocate (self, x, y, w, h):
		x, y = self.cr.user_to_device (x, y)
		w, h = self.cr.user_to_device_distance (w, h)
		self.extents = _extents_union (self.extents, [x, y, w, h])

	def set_allocation (self, x, y, w, h):
		x, y = self.cr.user_to_device (x, y)
		w, h = self.cr.user_to_device_distance (w, h)
		self.extents = [x, y, w, h]

	def create_layout (self, text, markup=True):

		cr = self.cr
		text = _remove_empty_lines (text)

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

		w,h = layout.get_size ()
		if s and w and h:
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

	def put_text (self, text, width=0, height=0, halign=0, valign=0, markup=True, alloc=True, desc=None, align=None):
		layout = self.create_layout (text, markup=markup)
		if desc:
			layout.set_font_description (pango.FontDescription (desc))
		if align != None:
			layout.set_alignment (align)
		elif halign < 0:
			layout.set_alignment (pango.ALIGN_RIGHT)
		elif halign > 0:
			layout.set_alignment (pango.ALIGN_LEFT)
		else:
			layout.set_alignment (pango.ALIGN_CENTER)

		width, height = self.fit_layout (layout, width, height)
		self.cr.rel_move_to ((halign - 1) * width / 2., (valign - 1) * height / 2.)
		x, y = self.cr.get_current_point ()
		self.cr.show_layout (layout)
		if alloc:
			self.allocate (x, y, width, height)
		return width, height

	def put_image (self, filename, width=0, height=0, halign=0, valign=0, alloc=True):

		global pixcache
		pix, w, h = pixcache.get (filename, (None, 0, 0))

		svg = filename.endswith (".svg")

		if not pix:
			if svg:
				pix = rsvg.Handle (filename)
				w, h = pix.get_dimension_data()[2:4]
			else:
				opaque = filename.endswith (".jpg")
				pix = gtk.gdk.pixbuf_new_from_file (filename)
				w, h = pix.get_width(), pix.get_height()
				if opaque:
					content = cairo.CONTENT_COLOR
				else:
					content = cairo.CONTENT_COLOR_ALPHA
				surface = self.get_target().create_similar (content, w, h)
				gcr = gtk.gdk.CairoContext (cairo.Context (surface))
				gcr.set_source_pixbuf (pix, 0, 0)
				if opaque:
					gcr.set_operator (cairo.OPERATOR_SOURCE)
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
		if alloc:
			self.allocate (0, 0, w, h)
		cr.restore ()
		return w * r, h * r

pixcache = {}


def main():
	import sys, getopt

	opts, args = getopt.gnu_getopt (sys.argv[1:], "o:t:sd:rf", ("output=", "theme=", "slideshow", "delay=", "repeat", "fullscreen"))

	if not args:
		print \
"""
Usage: slippy.py [--output output.pdf/ps/svg] [--theme theme.py] \\
		 [--slideshow [--delay seconds]] [--repeat] [--fullscreen] \\
		 slides.py..."""
		sys.exit (1)

	slidefiles = args
	themefile = None
	outputfile = None
	slideshow = False
	delay = 5.
	repeat = False
	fullscreen = False
	for opt, val in opts:
		if opt in ['-o', '--output']:
			outputfile = val
		elif opt in ['-t', '--theme']:
			themefile = val
		elif opt in ['-s', '--slideshow']:
			slideshow = True
		elif opt in ['-d', '--delay']:
			delay = float (val)
		elif opt in ['-r', '--repeat']:
			repeat = True
		elif opt in ['-f', '--fullscreen']:
			fullscreen = True

	def load_slides (slidefiles, args):
		all_slides = []
		for slidefile in slidefiles:
			slides = dict (args)
			execfile(slidefile, slides)
			all_slides += slides['slides']
		return all_slides

	def load_theme (themefile):
		if not themefile:
			return None
		themedict = dict ()
		execfile(themefile, themedict)
		class Theme:
			def __nonzero__ (self):
				return True
			def __getattr__ (self, attr):
				return themedict[attr]
		return Theme ()

	theme = load_theme (themefile)
	slides = load_slides (slidefiles, {'outputfile': outputfile})
	if outputfile:
		viewer = ViewerFile (outputfile)
	else:
		viewer = ViewerGTK (fullscreen=fullscreen, repeat=repeat, slideshow=slideshow, delay=delay)
	viewer.run (slides, theme=theme)

if __name__ == "__main__":
	main()

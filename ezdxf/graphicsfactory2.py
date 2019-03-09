# Created: 10.03.2013
# Copyright (c) 2013-2018, Manfred Moitzi
# License: MIT License
from typing import TYPE_CHECKING, Iterable, Sequence, Dict, Tuple, cast
import math
import logging

from ezdxf.lldxf import const
from ezdxf.lldxf.const import DXFValueError, DXFVersionError, DXF2000, DXF2007
from ezdxf.math import Vector
from ezdxf.math import bspline_control_frame, bspline_control_frame_approx
from ezdxf.render.arrows import ARROWS
from ezdxf.dimstyleoverride import DimStyleOverride
from ezdxf.render.dimension import multi_point_linear_dimension

logger = logging.getLogger('ezdxf')

if TYPE_CHECKING:  # import forward references
    from ezdxf.eztypes import LoftedSurface
    from ezdxf.eztypes import Solid3d, Region, Body, Surface, RevolvedSurface, ExtrudedSurface, SweptSurface

    from ezdxf.eztypes2 import UCS, Vertex, Drawing, DXFGraphic, DimStyleOverride
    from ezdxf.eztypes2 import Line, Arc, Circle, Point, Polyline, Shape, DXFEntity, Solid, Trace, Face3d
    from ezdxf.eztypes2 import Insert, Attrib, Polyface, Polymesh, Text, LWPolyline, Ellipse, MText, XLine, Ray, Spline
    from ezdxf.eztypes2 import Mesh, Hatch, Image, ImageDef, Underlay, UnderlayDef


class CreatorInterface:
    def __init__(self, doc: 'Drawing'):
        self.doc = doc

    # todo: for compatibility
    @property
    def drawing(self):
        return self.doc

    @property
    def dxfversion(self) -> str:
        return self.doc.dxfversion

    @property
    def dxffactory(self):
        return self.doc.dxffactory

    @property
    def is_active_paperspace(self):
        return False

    def new_entity(self, type_: str, dxfattribs: dict) -> 'DXFGraphic':
        """
        Create entity in drawing database and add entity to the entity space.

        Args:
            type_ (str): DXF type string, like 'LINE', 'CIRCLE' or 'LWPOLYLINE'
            dxfattribs (dict): DXF attributes for the new entity

        """
        entity = self.dxffactory.create_db_entry(type_, dxfattribs)
        self.add_entity(entity)
        return entity

    def add_entity(self, entity: 'DXFGraphic') -> None:
        pass

    def add_point(self, location: 'Vertex', dxfattribs: dict = None) -> 'Point':
        """
        Add a :class:`Point` element at `location`.

        Args:
            location: 2D/3D point in :ref:`WCS`
            dxfattribs (dist): additional DXF attributes for :class:`Point` entity

        Returns: :class:`Point`

        """
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['location'] = location
        return self.new_entity('POINT', dxfattribs)

    def add_line(self, start: 'Vertex', end: 'Vertex', dxfattribs: dict = None) -> 'Line':
        """
        Add a :class:`Line` element from `start` to `end`.

        Args:
            start: 2D/3D point in :ref:`WCS`
            end: 2D/3D point in :ref:`WCS`
            dxfattribs (dict): additional DXF attributes for :class:`Line` entity

        Returns: :class:`Line`

        """
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['start'] = start
        dxfattribs['end'] = end
        return self.new_entity('LINE', dxfattribs)

    def add_circle(self, center: 'Vertex', radius: float, dxfattribs: dict = None) -> 'Circle':
        """
        Add a :class:`Circle` element. This is an 2D element, which can be placed in space by using :ref:`OCS`.

        Args:
            center: 2D/3D point in :ref:`WCS`
            radius: circle radius
            dxfattribs (dcit): additional DXF attributes for :class:`Circle` entity

        Returns: :class:`Circle`

        """
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['center'] = center
        dxfattribs['radius'] = radius
        return self.new_entity('CIRCLE', dxfattribs)

    def add_ellipse(self, center: 'Vertex', major_axis: 'Vertex' = (1, 0, 0), ratio: float = 1, start_param: float = 0,
                    end_param: float = 2 * math.pi, dxfattribs: dict = None) -> 'Ellipse':
        """
        Add an :class:`Ellipse` element, `ratio` is the ratio of minor axis to major axis, `start_param` and `end_param`
        defines start and end point of the ellipse, a full ellipse goes from 0 to 2*pi. The ellipse goes from start to
        end param in `counter clockwise` direction.

        Args:
            center: center of ellipse as 2D/3D point in :ref:`WCS`
            major_axis: major axis as vector (x, y, z)
            ratio: ratio of minor axis to major axis
            start_param: start of ellipse curve
            end_param: end param of ellipse curve
            dxfattribs (dict): additional DXF attributes for :class:`Ellipse` entity

        Returns: :class:`Ellipse`

        """
        if self.dxfversion < 'AC1015':
            raise DXFVersionError('ELLIPSE requires DXF version R2000+')
        if ratio > 1.:
            raise DXFValueError("Parameter 'ratio' has to be <= 1.0")

        dxfattribs = dict(dxfattribs or {})
        dxfattribs['center'] = center
        dxfattribs['major_axis'] = major_axis
        dxfattribs['ratio'] = ratio
        dxfattribs['start_param'] = start_param
        dxfattribs['end_param'] = end_param
        return self.new_entity('ELLIPSE', dxfattribs)

    def add_arc(self, center: 'Vertex', radius: float, start_angle: float, end_angle: float,
                is_counter_clockwise: bool = True, dxfattribs: dict = None) -> 'Arc':
        """
        Add an :class:`Arc` element. The arc goes from `start_angle` to `end_angle` in counter clockwise
        direction by default, set parameter `is_counter_clockwise` to False for clockwise orientation.

        Args:
            center: center of arc as 2D/3D point in :ref:`WCS`
            radius: arc radius
            start_angle: start angle in degrees
            end_angle: end angle in degrees
            is_counter_clockwise: False for clockwise orientation
            dxfattribs (dict): additional DXF attributes for :class:`Arc` entity

        Returns: :class:`Arc`

        """
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['center'] = center
        dxfattribs['radius'] = radius
        if is_counter_clockwise:
            dxfattribs['start_angle'] = start_angle
            dxfattribs['end_angle'] = end_angle
        else:
            dxfattribs['start_angle'] = end_angle
            dxfattribs['end_angle'] = start_angle
        return self.new_entity('ARC', dxfattribs)

    def add_solid(self, points: Iterable['Vertex'], dxfattribs: dict = None) -> 'Solid':
        """
        Add a :class:`Solid` element, `points` is an iterable of 3 or 4 points.

        Args:
            points: iterable of 3 or 4 2D/3D points in :ref:`WCS`
            dxfattribs (dict): additional DXF attributes for :class:`Solid` entity

        Returns: :class:`Solid`

        """
        return cast('Solid', self._add_quadrilateral('SOLID', points, dxfattribs))

    def add_trace(self, points: Iterable['Vertex'], dxfattribs: dict = None) -> 'Trace':
        """
        Add a :class:`Trace` element, `points` is an iterable of 3 or 4 points.

        Args:
            points: iterable of 3 or 4 2D/3D points in :ref:`WCS`
            dxfattribs (dict): additional DXF attributes for :class:`Trace` entity

        Returns: :class:`Trace`

        """
        return cast('Trace', self._add_quadrilateral('TRACE', points, dxfattribs))

    def add_3dface(self, points: Iterable['Vertex'], dxfattribs: dict = None) -> 'Face3d':
        """
        Add a :class:`3DFace` element, `points` is an iterable 3 or 4 2D/3D points.

        Args:
            points: iterable of 3 or 4 2D/3D points in :ref:`WCS`
            dxfattribs (dict): additional DXF attributes for :class:`3DFace` entity

        Returns: :class:`3DFace`

        """
        return cast('Face', self._add_quadrilateral('3DFACE', points, dxfattribs))

    def add_text(self, text: str, dxfattribs: dict = None) -> 'Text':
        """
        Add a :class:`Text` element, see also :class:`Style`.

        Args:
            text: content string
            dxfattribs (dict): additional DXF attributes for :class:`Text` entity

        Returns: :class:`Text`

        """
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['text'] = text
        dxfattribs.setdefault('insert', Vector())
        return self.new_entity('TEXT', dxfattribs)

    def add_blockref(self, name: str, insert: 'Vertex', dxfattribs: dict = None) -> 'Insert':
        """
        Add an :class:`Insert` element.

        Args:
            name: block name
            insert: insert location as 2D/3D point in :ref:`WCS`
            dxfattribs (dict): additional DXF attributes for :class:`Insert` entity

        Returns: :class:`Insert`

        """
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['name'] = name
        dxfattribs['insert'] = insert
        blockref = self.new_entity('INSERT', dxfattribs)  # type: Insert
        return blockref

    def add_auto_blockref(self, name: str, insert: 'Vertex', values: Dict[str, str], dxfattribs: dict = None) \
            -> 'Insert':
        """
        Add an :class:`Insert` element. This method adds for each :class:`Attdef` entity, defined in the block
        definition, automatically an :class:`Attrib` entity to the block reference and set tag/value DXF attributes of
        the Attrib entities. The `values` dict defines the tag/value attributes as key=tag, value=tag value as string.
        The Attrib entities are placed relative to the insert point, which is equal to the block base point.

        Args:
            name: block name
            insert: insert location as 2D/3D point in :ref:`WCS`
            values (dict): :class:`Attrib` tag values as key=tag, value=tag value pairs
            dxfattribs (dict): additional DXF attributes for :class:`Insert` entity

        Returns: :class:`Insert`

        """

        def get_dxfattribs(attdef) -> dict:
            dxfattribs = attdef.dxfattribs()
            dxfattribs.pop('prompt', None)
            dxfattribs.pop('handle', None)
            return dxfattribs

        def unpack(dxfattribs) -> Tuple[str, str, 'Vertex']:
            tag = dxfattribs.pop('tag')
            text = values.get(tag, "")
            insert = dxfattribs.pop('insert')
            return tag, text, insert

        def autofill(blockref, blockdef) -> None:
            # ATTRIBs are placed relative to the base point
            for attdef in blockdef.attdefs():
                dxfattribs = get_dxfattribs(attdef)
                tag, text, insert = unpack(dxfattribs)
                blockref.add_attrib(tag, text, insert, dxfattribs)

        dxfattribs = dict(dxfattribs or {})
        autoblock = self.doc.blocks.new_anonymous_block()
        blockref = autoblock.add_blockref(name, (0, 0))
        blockdef = self.doc.blocks[name]
        autofill(blockref, blockdef)
        return self.add_blockref(autoblock.name, insert, dxfattribs)

    def add_attrib(self, tag: str, text: str, insert: 'Vertex' = (0, 0), dxfattribs: dict = None) -> 'Attrib':
        """
        Add an :class:`Attrib` as stand alone DXF entity.

        Args:
            tag: tag name as string
            text: tag value as string
            insert: insert location as 2D/3D point in :ref:`WCS`
            dxfattribs (dict): additional DXF attributes for :class:`Attrib` entity

        Returns: :class:`Attrib`

        """
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['tag'] = tag
        dxfattribs['text'] = text
        dxfattribs['insert'] = insert
        return self.new_entity('ATTRIB', dxfattribs)

    def add_polyline2d(self, points: Iterable['Vertex'], dxfattribs: dict = None) -> 'Polyline':
        """
        Add a 2D :class:`Polyline` entity.

        Args:
            points: iterable of 2D points in :ref:`WCS`
            dxfattribs (dict): additional DXF attributes for :class:`Polyline` entity

        Returns: :class:`Polyline`

        """
        dxfattribs = dict(dxfattribs or {})
        closed = dxfattribs.pop('closed', False)
        polyline = self.new_entity('POLYLINE', dxfattribs)  # type: Polyline
        polyline.close(closed)
        polyline.append_vertices(points)
        return polyline

    def add_polyline3d(self, points: Iterable['Vertex'], dxfattribs: dict = None) -> 'Polyline':
        """
        Add a 3D :class:`Polyline` entity.

        Args:
            points: iterable of 3D points in :ref:`WCS`
            dxfattribs (dict): additional DXF attributes for :class:`Polyline` entity

        Returns: :class:`Polyline`

        """
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['flags'] = dxfattribs.get('flags', 0) | const.POLYLINE_3D_POLYLINE
        return self.add_polyline2d(points, dxfattribs)

    def add_polymesh(self, size: Tuple[int, int] = (3, 3), dxfattribs: dict = None) -> 'Polymesh':
        """
        Add a :class:`Polymesh` entity, which is represented as :class:`Polyline` entity in the DXF file.
        A polymesh is a grid of `mcount` x `ncount` vertices and every vertex has its own xyz-coordinates.

        Args:
            size: 2-tuple (`mcount`, `ncount`)
            dxfattribs (dict): additional DXF attributes for :class:`Polyline` entity

        Returns: :class:`Polymesh`

        """
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['flags'] = dxfattribs.get('flags', 0) | const.POLYLINE_3D_POLYMESH
        m_size = max(size[0], 2)
        n_size = max(size[1], 2)
        dxfattribs['m_count'] = m_size
        dxfattribs['n_count'] = n_size
        m_close = dxfattribs.pop('m_close', False)
        n_close = dxfattribs.pop('n_close', False)
        polymesh = self.new_entity('POLYLINE', dxfattribs)  # type: Polymesh

        points = [(0, 0, 0)] * (m_size * n_size)
        polymesh.append_vertices(points)  # init mesh vertices
        polymesh.close(m_close, n_close)
        return polymesh.cast()

    def add_polyface(self, dxfattribs: dict = None) -> 'Polyface':
        """
        Add a :class:`Polyface` entity, which is represented as :class:`Polyline` entity in the DXF file.

        Args:
            dxfattribs (dict): additional DXF attributes for :class:`Polyline` entity

        Returns: :class:`Polyface`

        """
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['flags'] = dxfattribs.get('flags', 0) | const.POLYLINE_POLYFACE
        m_close = dxfattribs.pop('m_close', False)
        n_close = dxfattribs.pop('n_close', False)
        polyface = self.new_entity('POLYLINE', dxfattribs)  # type: Polyface
        polyface.close(m_close, n_close)
        return polyface.cast()

    def _add_quadrilateral(self, type_: str, points: Iterable['Vertex'], dxfattribs: dict = None) -> 'DXFGraphic':
        dxfattribs = dict(dxfattribs or {})
        entity = self.new_entity(type_, dxfattribs)
        for x, point in enumerate(self._four_points(points)):
            entity[x] = point
        return entity

    @staticmethod
    def _four_points(points: Iterable['Vertex']) -> Iterable['Vertex']:
        vertices = list(points)
        if len(vertices) not in (3, 4):
            raise DXFValueError('3 or 4 points required.')
        for vertex in vertices:
            yield vertex
        if len(vertices) == 3:
            yield vertices[-1]  # last again

    def add_shape(self, name: str, insert: 'Vertex' = (0, 0), size: float = 1.0, dxfattribs: dict = None) -> 'Shape':
        """
        Add a :class:`Shape` reference to a external stored shape.

        Args:
            name: shape name as string
            insert: insert location as 2D/3D point in :ref:`WCS`
            size: size factor
            dxfattribs (dict): additional DXF attributes for :class:`Shape` entity

        Returns: :class:`Shape`

        """
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['name'] = name
        dxfattribs['insert'] = insert
        dxfattribs['size'] = size
        return self.new_entity('SHAPE', dxfattribs)

    # new entities in DXF AC1015 (R2000)

    def add_lwpolyline(self, points: Iterable['Vertex'], format: str = 'xyseb',
                       dxfattribs: dict = None) -> 'LWPolyline':
        """
        Add a 2D polyline as :class:`LWPolyline` entity. A points are defined as (x, y, [start_width, [end_width,
        [bulge]]]) tuples, but order can be redefined by the `format` argument. Set start_width, end_width to 0 to be
        ignored (x, y, 0, 0, bulge).

        The :class:`LWPolyline` is defined as a single DXF entity and needs less disk space and memory than a
        :class:`Polyline` entity. (requires DXF R2000+)

        Args:
            points: iterable of (x, y, [start_width, [end_width, [bulge]]]) tuples
            format: user defined point format, default is "xyseb"
            dxfattribs (dict): additional DXF attributes for :class:`LWPolyline` entity

        Returns: :class:`LWPolyline`

        """
        if self.dxfversion < DXF2000:
            raise DXFVersionError('LWPOLYLINE requires DXF version R2000+')
        dxfattribs = dict(dxfattribs or {})
        closed = dxfattribs.pop('closed', False)
        lwpolyline = self.new_entity('LWPOLYLINE', dxfattribs)  # type: LWPolyline
        lwpolyline.set_points(points, format=format)
        lwpolyline.closed = closed
        return lwpolyline

    def add_mtext(self, text: str, dxfattribs: dict = None) -> 'MText':
        """
        Add a multiline text element with automatic text wrapping at boundaries as :class:`MText` entity. (requires
        DXF R2000+)

        Args:
            text: content string
            dxfattribs (dict): additional DXF attributes for :class:`MText` entity

        Returns: :class:`MText`

        """
        if self.dxfversion < DXF2000:
            raise DXFVersionError('MTEXT requires DXF version R2000+')
        dxfattribs = dict(dxfattribs or {})
        mtext = self.new_entity('MTEXT', dxfattribs)  # type: MText
        mtext.text = text
        return mtext

    def add_ray(self, start: 'Vertex', unit_vector: 'Vertex', dxfattribs: dict = None) -> 'Ray':
        """
        Add a :class:`Ray` that begins at `start` point and continues to infinity (construction line).
        (requires DXF R2000+)

        Args:
            start: location 3D point in :ref:`WCS`
            unit_vector: 3D vector (x, y, z)
            dxfattribs (dict): additional DXF attributes for :class:`Ray` entity

        Returns: :class:`Ray`

        """
        if self.dxfversion < DXF2000:
            raise DXFVersionError('RAY requires DXF version R2000+')
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['start'] = start
        dxfattribs['unit_vector'] = unit_vector
        return self.new_entity('RAY', dxfattribs)

    def add_xline(self, start: 'Vertex', unit_vector: 'Vertex', dxfattribs: dict = None) -> 'XLine':
        """
        Add an infinity :class:`XLine` (construction line).
        (requires DXF R2000+)

        Args:
            start: location 3D point in :ref:`WCS`
            unit_vector: 3D vector (x, y, z)
            dxfattribs (dict): additional DXF attributes for :class:`XLine` entity

        Returns: :class:`XLine`

        """
        if self.dxfversion < DXF2000:
            raise DXFVersionError('XLINE requires DXF version R2000+')
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['start'] = start
        dxfattribs['unit_vector'] = unit_vector
        return self.new_entity('XLINE', dxfattribs)

    def add_spline(self, fit_points: Iterable['Vertex'] = None, degree: int = 3, dxfattribs: dict = None) -> 'Spline':
        """
        Add a B-spline defined by fit points, the control points and knot values are created by the CAD application,
        therefore it is not predictable how the rendered spline will look like, because for every set of fit points
        exists an infinite set of B-splines. If fit_points is None, an 'empty' spline will be created, all data has to
        be set by the user. (requires DXF R2000+)

        AutoCAD creates a spline through fit points by a proprietary algorithm. `ezdxf` can not reproduce the control
        point calculation.

        Args:
            fit_points: iterable of fit points as (x, y[, z]) in :ref:`WCS`, if None -> user defined spline
            degree: degree fo B-spline
            dxfattribs (dict): additional DXF attributes for :class:`Spline` entity

        Returns: :class:`Spline`

        """
        if self.dxfversion < DXF2000:
            raise DXFVersionError('SPLINE requires DXF version R2000+')
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['degree'] = degree
        spline = self.new_entity('SPLINE', dxfattribs)  # type: Spline
        if fit_points is not None:
            spline.fit_points = fit_points
        return spline

    def add_spline_control_frame(self, fit_points: Iterable['Vertex'], degree: int = 3, method: str = 'distance',
                                 power: float = .5, dxfattribs: dict = None) -> 'Spline':
        """
        Create and add B-spline control frame from fit points.

            1. method = "uniform", creates a uniform t vector, [0...1] equally spaced
            2. method = "distance", creates a t vector with values proportional to the fit point distances
            3. method = "centripetal", creates a t vector with values proportional to the fit point distances^power

        None of this methods matches the spline created from fit points by AutoCAD.

        Args:
            fit_points: iterable of fit points as (x, y[, z]) in :ref:`WCS`
            degree: degree of B-spline
            method: calculation method for parameter vector t
            power: power for centripetal method
            dxfattribs (dict): additional DXF attributes for :class:`Spline` entity

        Returns: :class:`Spline`

        """
        bspline = bspline_control_frame(fit_points, degree=degree, method=method, power=power)
        return self.add_open_spline(
            control_points=bspline.control_points,
            degree=bspline.degree,
            knots=bspline.knot_values(),
            dxfattribs=dxfattribs,
        )

    def add_spline_approx(self, fit_points: Iterable['Vertex'], count: int, degree: int = 3, method: str = 'distance',
                          power: float = .5, dxfattribs: dict = None) -> 'Spline':
        """
        Approximate B-spline by a reduced count of control points, given are the fit points and the degree of the B-spline.

            1. method = 'uniform', creates a uniform t vector, [0...1] equally spaced
            2. method = 'distance', creates a t vector with values proportional to the fit point distances
            3. method = 'centripetal', creates a t vector with values proportional to the fit point distances^power

        (requires DXF R2000+)

        Args:
            fit_points: all fit points of B-spline
            count: count of designated control points
            degree: degree of B-spline
            method: calculation method for parameter vector t
            power: power for centripetal method
            dxfattribs (dict): additional DXF attributes for :class:`Spline` entity

        Returns: :class:`Spline`

        """
        bspline = bspline_control_frame_approx(fit_points, count, degree=degree, method=method, power=power)
        return self.add_open_spline(
            control_points=bspline.control_points,
            degree=bspline.degree,
            dxfattribs=dxfattribs,
        )

    def add_open_spline(self, control_points: Iterable['Vertex'], degree: int = 3, knots: Iterable[float] = None,
                        dxfattribs: dict = None) -> 'Spline':
        """
        Add an open uniform :class:`Spline` defined by `control_points`. (requires DXF R2000+)

        Open uniform B-splines start and end at your first and last control point.

        Args:
            control_points: iterable of 3D points in :ref:`WCS`
            degree: degree of B-spline
            knots: knot values as iterable of floats
            dxfattribs (dict): additional DXF attributes for :class:`Spline` entity

        Returns: :class:`Spline`

        """
        spline = self.add_spline(dxfattribs=dxfattribs)
        spline.set_open_uniform(list(control_points), degree)
        if knots is not None:
            spline.knots = knots
        return spline

    def add_closed_spline(self, control_points: Iterable['Vertex'], degree: int = 3, knots: Iterable[float] = None,
                          dxfattribs: dict = None) -> 'Spline':
        """
        Add a closed uniform :class:`Spline` defined by `control_points`. (requires DXF R2000+)

        Closed uniform B-splines is a closed curve start and end at the first control point.

        Args:
            control_points: iterable of 3D points in :ref:`WCS`
            degree: degree of B-spline
            knots: knot values as iterable of floats
            dxfattribs (dict): additional DXF attributes for :class:`Spline` entity

        Returns: :class:`Spline`

        """
        spline = self.add_spline(dxfattribs=dxfattribs)
        spline.set_periodic(list(control_points), degree)
        if knots is not None:
            spline.knots = knots
        return spline

    def add_rational_spline(self, control_points: Iterable['Vertex'], weights: Sequence[float], degree: int = 3,
                            knots: Iterable[float] = None, dxfattribs: dict = None) -> 'Spline':
        """
        Add an open rational uniform :class:`Spline` defined by `control_points`. (requires DXF R2000+)

        `weights` has to be an iterable of floats, which defines the influence of the associated control point to the
        shape of the B-spline, therefore for each control point is one weight value required.

        Open rational uniform B-splines start and end at the first and last control point.

        Args:
            control_points: iterable of 3D points in :ref:`WCS`
            weights: weight values as iterable of floats
            degree: degree of B-spline
            knots: knot values as iterable of floats
            dxfattribs (dict): additional DXF attributes for :class:`Spline` entity

        Returns: :class:`Spline`

        """
        spline = self.add_spline(dxfattribs=dxfattribs)
        spline.set_open_rational(list(control_points), weights, degree)
        if knots is not None:
            spline.knots = knots
        return spline

    def add_closed_rational_spline(self, control_points: Iterable['Vertex'], weights: Sequence[float], degree: int = 3,
                                   knots: Iterable[float] = None, dxfattribs: dict = None) -> 'Spline':
        """
        Add a closed rational uniform :class:`Spline` defined by  `control_points`. (requires DXF R2000+)

        `weights` has to be an iterable of floats, which defines the influence of the associated control point to the
        shape of the B-spline, therefore for each control point is one weight value required.

        Closed rational uniform B-splines start and end at the first control point.

        Args:
            control_points: iterable of 3D points in :ref:`WCS`
            weights: weight values as iterable of floats
            degree: degree of B-spline
            knots: knot values as iterable of floats
            dxfattribs (dict): additional DXF attributes for :class:`Spline` entity

        Returns: :class:`Spline`

        """
        spline = self.add_spline(dxfattribs=dxfattribs)
        spline.set_periodic_rational(list(control_points), weights, degree)
        if knots is not None:
            spline.knots = knots
        return spline

    def add_body(self, acis_data: str = None, dxfattribs: dict = None) -> 'Body':
        """
        Add a :class:`Body` entity. (requires DXF R2000+)

        Args:
            acis_data: ACIS data as iterable of text lines as strings, no interpretation by ezdxf possible
            dxfattribs (dict): additional DXF attributes for :class:`Body` entity

        Returns: :class:`Body`

        """
        return self._add_acis_entiy('BODY', acis_data, dxfattribs)

    def add_region(self, acis_data: str = None, dxfattribs: dict = None) -> 'Region':
        """
        Add a :class:`Region` entity. (requires DXF R2000+)

        Args:
            acis_data: ACIS data as iterable of text lines as strings, no interpretation by ezdxf possible
            dxfattribs (dict): additional DXF attributes for :class:`Region` entity

        Returns: :class:`Region`

        """
        return cast('Region', self._add_acis_entiy('REGION', acis_data, dxfattribs))

    def add_3dsolid(self, acis_data: str = None, dxfattribs: dict = None) -> 'Solid3d':
        """
        Add a :class:`3DSolid` entity. (requires DXF R2000+)

        Args:
            acis_data: ACIS data as iterable of text lines as strings, no interpretation by ezdxf possible
            dxfattribs (dict): additional DXF attributes for :class:`3DSolid` entity

        Returns: :class:`3DSolid`

        """
        return cast('Solid3d', self._add_acis_entiy('3DSOLID', acis_data, dxfattribs))

    def add_surface(self, acis_data: str = None, dxfattribs: dict = None) -> 'Surface':
        """
        Add a :class:`Surface` entity. (requires DXF R2007+)

        Args:
            acis_data: ACIS data as iterable of text lines as strings, no interpretation by ezdxf possible
            dxfattribs (dict): additional DXF attributes for :class:`Surface` entity

        Returns: :class:`Surface`

        """
        if self.dxfversion < DXF2007:
            raise DXFVersionError('SURFACE requires DXF version R2007+')
        return cast('Surface', self._add_acis_entiy('SURFACE', acis_data, dxfattribs))

    def add_extruded_surface(self, acis_data: str = None, dxfattribs: dict = None) -> 'ExtrudedSurface':
        """
        Add a :class:`ExtrudedSurface` entity. (requires DXF R2007+)

        Args:
            acis_data: ACIS data as iterable of text lines as strings, no interpretation by ezdxf possible
            dxfattribs (dict): additional DXF attributes for :class:`ExtrudedSurface` entity

        Returns: :class:`ExtrudedSurface`

        """
        if self.dxfversion < DXF2007:
            raise DXFVersionError('EXTRUDEDSURFACE requires DXF version R2007+')
        return cast('ExtrudedSurface', self._add_acis_entiy('EXTRUDEDSURFACE', acis_data, dxfattribs))

    def add_lofted_surface(self, acis_data: str = None, dxfattribs: dict = None) -> 'LoftedSurface':
        """
        Add a :class:`LoftedSurface` entity. (requires DXF R2007+)

        Args:
            acis_data: ACIS data as iterable of text lines as strings, no interpretation by ezdxf possible
            dxfattribs (dict): additional DXF attributes for :class:`LoftedSurface` entity

        Returns: :class:`LoftedSurface`

        """
        if self.dxfversion < DXF2007:
            raise DXFVersionError('LOFTEDSURFACE requires DXF version R2007+')
        return cast('LoftedSurface', self._add_acis_entiy('LOFTEDSURFACE', acis_data, dxfattribs))

    def add_revolved_surface(self, acis_data: str = None, dxfattribs: dict = None) -> 'RevolvedSurface':
        """
        Add a :class:`RevolvedSurface` entity. (requires DXF R2007+)

        Args:
            acis_data: ACIS data as iterable of text lines as strings, no interpretation by ezdxf possible
            dxfattribs (dict): additional DXF attributes for :class:`RevolvedSurface` entity

        Returns: :class:`RevolvedSurface`

        """
        if self.dxfversion < DXF2007:
            raise DXFVersionError('REVOLVEDSURFACE requires DXF version R2007+')
        return cast('RevolvedSurface', self._add_acis_entiy('REVOLVEDSURFACE', acis_data, dxfattribs))

    def add_swept_surface(self, acis_data: str = None, dxfattribs: dict = None) -> 'SweptSurface':
        """
        Add a :class:`SweptSurface` entity. (requires DXF R2007+)

        Args:
            acis_data: ACIS data as iterable of text lines as strings, no interpretation by ezdxf possible
            dxfattribs (dict): additional DXF attributes for :class:`SweptSurface` entity

        Returns: :class:`SweptSurface`

        """
        if self.dxfversion < DXF2007:
            raise DXFVersionError('SWEPT requires DXF version R2007+')
        return cast('SweptSurface', self._add_acis_entiy('SWEPTSURFACE', acis_data, dxfattribs))

    def _add_acis_entiy(self, name, acis_data: str, dxfattribs: dict) -> 'Body':
        if self.dxfversion < DXF2000:
            raise DXFVersionError('{} requires DXF version R2000+'.format(name))
        dxfattribs = dict(dxfattribs or {})
        entity = self.new_entity(name, dxfattribs)  # type: Body
        if acis_data is not None:
            entity.set_acis_data(acis_data)
        return entity

    def add_hatch(self, color: int = 7, dxfattribs: dict = None) -> 'Hatch':
        """
        Add a :class:`Hatch` entity. (requires DXF R2007+)

        Args:
            color: ACI (AutoCAD Color Index), default is 7 (black/white).
            dxfattribs (dict): additional DXF attributes for :class:`Hatch` entity

        Returns: :class:`Hatch`

        """
        if self.dxfversion < DXF2000:
            raise DXFVersionError('HATCH requires DXF version R2000+')
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['solid_fill'] = 1
        dxfattribs['color'] = color
        dxfattribs['pattern_name'] = 'SOLID'
        return self.new_entity('HATCH', dxfattribs)

    def add_mesh(self, dxfattribs: dict = None) -> 'Mesh':
        """
        Add a :class:`Mesh` entity. (requires DXF R2007+)

        Args:
            dxfattribs (dict): additional DXF attributes for :class:`Mesh` entity

        Returns: :class:`Mesh`

        """
        if self.dxfversion < DXF2000:
            raise DXFVersionError('MESH requires DXF version R2000+')
        dxfattribs = dict(dxfattribs or {})
        return self.new_entity('MESH', dxfattribs)

    def add_image(self, image_def: 'ImageDef', insert: 'Vertex', size_in_units: Tuple[float, float],
                  rotation: float = 0.,
                  dxfattribs: dict = None) -> 'Image':
        """
        Add an :class:`Image` entity. Create :class:`ImageDef` by the :class:`Drawing` factory function
        :meth:`~Drawing.add_image_def`, see :ref:`tut_image`. (requires DXF R2000+)

        Args:
            image_def: required image definition as :class:`ImageDef`
            insert: insertion point as 3D point in :ref:`WCS`
            size_in_units: size as (x, y) tuple in drawing units
            rotation: rotation angle around the z-axis in degrees
            dxfattribs (dict): additional DXF attributes for :class:`Image` entity

        Returns: :class:`Image`

        """

        def to_vector(units_per_pixel, angle_in_rad):
            x = math.cos(angle_in_rad) * units_per_pixel
            y = math.sin(angle_in_rad) * units_per_pixel
            return round(x, 6), round(y, 6), 0  # supports only images in the xy-plane

        if self.dxfversion < DXF2000:
            raise DXFVersionError('IMAGE requires DXF version R2000+')
        dxfattribs = dict(dxfattribs or {})
        x_pixels, y_pixels = image_def.dxf.image_size.vec2
        x_units, y_units = size_in_units
        x_units_per_pixel = x_units / x_pixels
        y_units_per_pixel = y_units / y_pixels
        x_angle_rad = math.radians(rotation)
        y_angle_rad = x_angle_rad + (math.pi / 2.)

        dxfattribs['insert'] = Vector(insert)
        dxfattribs['u_pixel'] = to_vector(x_units_per_pixel, x_angle_rad)
        dxfattribs['v_pixel'] = to_vector(y_units_per_pixel, y_angle_rad)
        dxfattribs['image_def_handle'] = image_def.dxf.handle
        dxfattribs['image_size'] = image_def.dxf.image_size

        image = self.new_entity('IMAGE', dxfattribs)  # type: Image
        if self.doc is not None:
            image_def_reactor = self.doc.objects.add_image_def_reactor(image.dxf.handle)
            reactor_handle = image_def_reactor.dxf.handle
            image.dxf.image_def_reactor_handle = reactor_handle
            image_def.append_reactor_handle(reactor_handle)
        return image

    def add_underlay(self, underlay_def: 'UnderlayDef', insert: 'Vertex' = (0, 0, 0),
                     scale=(1, 1, 1), rotation: float = 0., dxfattribs: dict = None) -> 'Underlay':
        """
        Add an :class:`Underlay` entity. Create :class:`UnderlayDef` by the :class:`Drawing` factory function
        :meth:`~Drawing.add_underlay_def`, see :ref:`tut_underlay`. (requires DXF R2000+)

        Args:
            underlay_def: required underlay definition as :class:`UnderlayDef`
            insert: insertion point as 3D point in :ref:`WCS`
            scale:  underlay scaling factor as (x, y, z) tuple or as single value for uniform scaling for x, y and z
            rotation: rotation angle around the z-axis in degrees
            dxfattribs (dict): additional DXF attributes for :class:`Underlay` entity

        Returns: :class:`Underlay`

        """
        if self.dxfversion < DXF2000:
            raise DXFVersionError('UNDERLAY requires DXF version R2000+')
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['insert'] = insert
        dxfattribs['underlay_def_handle'] = underlay_def.dxf.handle
        dxfattribs['rotation'] = rotation

        underlay = self.new_entity(underlay_def.entity_name, dxfattribs)  # type: Underlay
        underlay.scaling = scale
        underlay_def.append_reactor_handle(underlay.dxf.handle)
        return underlay

    def add_linear_dim(self,
                       base: 'Vertex',
                       p1: 'Vertex',
                       p2: 'Vertex',
                       location: 'Vertex' = None,
                       text: str = "<>",
                       angle: float = 0,  # 0=horizontal, 90=vertical, else=rotated
                       text_rotation: float = None,
                       dimstyle: str = 'EZDXF',
                       override: dict = None,
                       dxfattribs: dict = None) -> DimStyleOverride:
        """
        Add horizontal, vertical and rotated dimension line. If an :class:`UCS` is used for dimension line rendering,
        all point definitions in UCS coordinates, translation into :ref:`WCS` and :ref:`OCS` is done by the rendering
        function. Manual set extrusion vector will be replaced by OCS defined by UCS or (0, 0, 1) if no UCS is used.

        This method returns a :class:`DimStyleOverride` object, to create the necessary dimension geometry, you have to
        call :meth:`DimStyleOverride.render` manually, this two step process allows additional processing steps on the
        :class:`Dimension` entity between creation and rendering.

        Args:
            base: location of dimension line, any point on the dimension line or its extension will do (in UCS)
            p1: measurement point 1 and start point of extension line 1 (in UCS)
            p2: measurement point 2 and start point of extension line 2 (in UCS)
            location: user defined location for text mid point (in UCS)
            text: None or "<>" the measurement is drawn as text, " " (one space) suppresses the dimension text,
                  everything else `text` is drawn as dimension text
            dimstyle: dimension style name (:class:`DimStyle` table entry), default is "EZDXF"
            angle: angle from ucs/wcs x-axis to dimension line in degrees
            text_rotation: rotation angle of the dimension text away from its default orientation
                           (the direction of the dimension line) in degrees
            override: :class:`DimStyleOverride` attributes
            dxfattribs: DXF attributes for :class:`Dimension` entity

        Returns: :class:`DimStyleOverride`

        """
        type_ = {'dimtype': const.DIM_LINEAR | const.DIM_BLOCK_EXCLUSIVE}
        dimline = cast('Dimension', self.new_entity('DIMENSION', dxfattribs=type_))
        dxfattribs = dict(dxfattribs or {})
        dxfattribs['dimstyle'] = dimstyle
        dxfattribs['defpoint'] = Vector(base)
        dxfattribs['text'] = text
        dxfattribs['defpoint2'] = Vector(p1)
        dxfattribs['defpoint3'] = Vector(p2)
        dxfattribs['angle'] = float(angle)
        # text_rotation ALWAYS overrides implicit angles as absolute angle (0 is horizontal)!
        if text_rotation is not None:
            dxfattribs['text_rotation'] = float(text_rotation)
        dimline.update_dxf_attribs(dxfattribs)

        style = DimStyleOverride(dimline, override=override)
        if location is not None:
            style.set_location(location, leader=False, relative=False)
        return style

    def add_multi_point_linear_dim(self,
                                   base: 'Vertex',
                                   points: Iterable['Vertex'],
                                   angle: float = 0,
                                   ucs: 'UCS' = None,
                                   avoid_double_rendering: bool = True,
                                   dimstyle: str = 'EZDXF',
                                   override: dict = None,
                                   dxfattribs: dict = None,
                                   discard=False) -> None:
        """
        Add multiple linear dimensions for iterable `points`. If an :class:`UCS` is used for dimension line
        rendering, all point definitions in UCS coordinates, translation into :ref:`WCS` and :ref:`OCS` is done by the
        rendering function. Manual set extrusion vector will be replaced by OCS defined by UCS or (0, 0, 1) if no UCS
        is used.

        This method sets many design decisions by itself, the necessary geometry will be generated automatically, no
        required nor possible :meth:`render` call. This method is easy to use but you get what you get.

        Args:
            base: location of dimension line, any point on the dimension line or its extension will do (in UCS)
            points: iterable of measurement points (in UCS)
            angle: angle from ucs/wcs x-axis to dimension line in degrees (0=horizontal, 90=vertical)
            ucs: user defined coordinate system
            avoid_double_rendering: suppresses the first extension line and the first arrow if possible for continued
                                    dimension entities
            dimstyle: dimension style name (DimStyle table entry), default is "EZDXF"
            override: :class:`DimStyleOverride` attributes
            dxfattribs: DXF attributes for :class:`Dimension` entity
            discard: discard rendering result for friendly CAD applications like BricsCAD to get a native and likely
                     better rendering result. (does not work with AutoCAD)

        """
        multi_point_linear_dimension(
            cast('GenericLayoutType', self),
            base=base,
            points=points,
            angle=angle,
            ucs=ucs,
            avoid_double_rendering=avoid_double_rendering,
            dimstyle=dimstyle,
            override=override,
            dxfattribs=dxfattribs,
            discard=discard,
        )

    def add_aligned_dim(self,
                        p1: 'Vertex',
                        p2: 'Vertex',
                        distance: float,
                        text: str = "<>",
                        dimstyle: str = 'EZDXF',
                        override: dict = None,
                        dxfattribs: dict = None) -> DimStyleOverride:
        """
        Add linear dimension aligned with measurement points `p1` and `p2`. If an :class:`UCS` is used for dimension
        line rendering, all point definitions in UCS coordinates, translation into :ref:`WCS` and :ref:`OCS` is
        done by the rendering function. Manual set extrusion vector will be replaced by OCS defined by UCS or (0, 0, 1)
        if no UCS is used.

        This method returns a :class:`DimStyleOverride` object, to create the necessary dimension geometry, you have to
        call :meth:`DimStyleOverride.render` manually, this two step process allows additional processing steps on the
        :class:`Dimension` entity between creation and rendering.

        Args:
            p1: measurement point 1 and start point of extension line 1 (in UCS)
            p2: measurement point 2 and start point of extension line 2 (in UCS)
            distance: distance of dimension line from measurement points
            text: None or "<>" the measurement is drawn as text, " " (one space) suppresses the dimension text,
                  everything else `text` is drawn as dimension text
            dimstyle: dimension style name (:class:`DimStyle` table entry), default is "EZDXF"
            override: :class:`DimStyleOverride` attributes
            dxfattribs: DXF attributes for :class:`Dimension` entity

        Returns: :class:`DimStyleOverride`

        """
        p1 = Vector(p1)
        p2 = Vector(p2)
        direction = p2 - p1
        angle = direction.angle_deg
        base = direction.orthogonal().normalize(distance)
        return self.add_linear_dim(
            base=base,
            p1=p1,
            p2=p2,
            dimstyle=dimstyle,
            text=text,
            angle=angle,
            override=override,
            dxfattribs=dxfattribs,
        )

    def add_angular_dim(self, override: dict = None, dxfattribs: dict = None) -> DimStyleOverride:
        type_ = {'dimtype': const.DIM_ANGULAR | const.DIM_BLOCK_EXCLUSIVE}
        dimline = cast('Dimension', self.new_entity('DIMENSION', dxfattribs=type_).cast())
        dxfattribs = dict(dxfattribs or {})
        dimline.update_dxf_attribs(dxfattribs)
        style = DimStyleOverride(dimline, override=override)
        return style

    def add_diameter_dim(self, override: dict = None, dxfattribs: dict = None) -> DimStyleOverride:
        type_ = {'dimtype': const.DIM_DIAMETER | const.DIM_BLOCK_EXCLUSIVE}
        dimline = cast('Dimension', self.new_entity('DIMENSION', dxfattribs=type_).cast())
        dxfattribs = dict(dxfattribs or {})
        dimline.update_dxf_attribs(dxfattribs)
        style = DimStyleOverride(dimline, override=override)
        return style

    def add_radius_dim(self, override: dict = None, dxfattribs: dict = None) -> DimStyleOverride:
        type_ = {'dimtype': const.DIM_RADIUS | const.DIM_BLOCK_EXCLUSIVE}
        dimline = cast('Dimension', self.new_entity('DIMENSION', dxfattribs=type_).cast())
        dxfattribs = dict(dxfattribs or {})
        dimline.update_dxf_attribs(dxfattribs)
        style = DimStyleOverride(dimline, override=override)
        return style

    def add_angular_3p_dim(self, override: dict = None, dxfattribs: dict = None) -> DimStyleOverride:
        type_ = {'dimtype': const.DIM_ANGULAR_3P | const.DIM_BLOCK_EXCLUSIVE}
        dimline = cast('Dimension', self.new_entity('DIMENSION', dxfattribs=type_).cast())
        dxfattribs = dict(dxfattribs or {})
        dimline.update_dxf_attribs(dxfattribs)
        style = DimStyleOverride(dimline, override=override)
        return style

    def add_ordinate_dim(self, override: dict = None, dxfattribs: dict = None) -> DimStyleOverride:
        type_ = {'dimtype': const.DIM_ORDINATE | const.DIM_BLOCK_EXCLUSIVE}
        dimline = cast('Dimension', self.new_entity('DIMENSION', dxfattribs=type_).cast())
        dxfattribs = dict(dxfattribs or {})
        dimline.update_dxf_attribs(dxfattribs)
        style = DimStyleOverride(dimline, override=override)
        return style

    def add_arrow(self, name: str, insert: 'Vertex', size: float = 1., rotation: float = 0,
                  dxfattribs: dict = None) -> Vector:
        return ARROWS.render_arrow(self, name=name, insert=insert, size=size, rotation=rotation, dxfattribs=dxfattribs)

    def add_arrow_blockref(self, name: str, insert: 'Vertex', size: float = 1., rotation: float = 0,
                           dxfattribs: dict = None) -> Vector:
        return ARROWS.insert_arrow(self, name=name, insert=insert, size=size, rotation=rotation, dxfattribs=dxfattribs)

module MCPforSketchUp
  module Handlers
    module Inspection
      # Fixed read-only export surface. No Ruby evaluation, save-model or caller paths.
      def self.describe_entity(e)
        base = {
          'entity_id' => e.entityID, 'persistent_id' => e.persistent_id,
          'type' => e.typename, 'hidden' => e.hidden?,
          'layer' => e.layer.name, 'layer_visible' => e.layer.visible?
        }
        base['material'] = e.material&.name if e.respond_to?(:material)
        if e.is_a?(Sketchup::Group) || e.is_a?(Sketchup::ComponentInstance)
          base.merge!('name' => e.name, 'definition_id' => e.definition.entityID,
                      'definition_name' => e.definition.name,
                      'transform_inches' => e.transformation.to_a)
        elsif e.is_a?(Sketchup::Face)
          mesh = e.mesh(7)
          base.merge!(
            'back_material' => e.back_material&.name,
            'normal' => e.normal.to_a,
            'loops_inches' => e.loops.map { |loop| {
              'outer' => loop.outer?,
              'points' => loop.vertices.map { |v| v.position.to_a }
            } },
            'points_inches' => mesh.points.map(&:to_a),
            'polygons' => mesh.polygons,
            'uvq_front' => (1..mesh.count_points).map { |i| mesh.uv_at(i, true)&.to_a },
            'uvq_back' => (1..mesh.count_points).map { |i| mesh.uv_at(i, false)&.to_a }
          )
        end
        base
      end

      def self.get_source_scene(params)
        m = Helpers::Entities.active_model!
        {
          'path' => m.path, 'title' => m.title, 'guid' => m.guid,
          'modified' => m.modified?, 'sketchup_version' => Sketchup.version,
          'coordinate_units' => 'inches', 'transform_layout' => 'SketchUp column-major 4x4',
          'root_count' => m.entities.length,
          'definitions' => m.definitions.map { |d| {
            'id' => d.entityID, 'name' => d.name, 'count' => d.entities.length
          } }
        }
      end

      def self.get_source_entities(params)
        m = Helpers::Entities.active_model!
        id = params['definition_id']
        collection = if id.nil?
          m.entities
        else
          d = m.definitions.find { |v| v.entityID.to_s == id.to_s }
          raise ArgumentError, 'Unknown definition ID' unless d
          d.entities
        end
        offset = [[params.fetch('offset', 0).to_i, 0].max, collection.length].min
        limit = [[params.fetch('limit', 100).to_i, 1].max, 200].min
        page = collection.to_a.slice(offset, limit) || []
        {
          'total' => collection.length, 'offset' => offset,
          'entities' => page.map { |e| describe_entity(e) },
          'more' => offset + page.length < collection.length
        }
      end

      def self.get_source_texture(params)
        require 'tempfile'
        require 'base64'
        m = Helpers::Entities.active_model!
        mat = m.materials.find { |v| v.name == params['name'] }
        raise ArgumentError, 'Unknown textured material' unless mat && mat.texture
        colorized = params['colorized'] == true
        img = mat.texture.image_rep(colorized)
        png = nil
        Tempfile.create(['agr_source_texture_', '.png']) do |temp|
          temp.close
          img.save_file(temp.path)
          raise 'Texture extraction produced no image' unless File.file?(temp.path) && File.size(temp.path) > 8
          raise 'Texture exceeds transport limit' if File.size(temp.path) > 40 * 1024 * 1024
          png = File.binread(temp.path)
        end
        {
          'material' => mat.name, 'colorized' => colorized,
          'width' => img.width, 'height' => img.height,
          'png_base64' => Base64.strict_encode64(png)
        }
      end

      def self.get_materials(params)
        materials = Helpers::Entities.active_model!.materials.to_a
        offset = [[params.fetch('offset', 0).to_i, 0].max, materials.length].min
        limit = [[params.fetch('limit', 50).to_i, 1].max, 200].min
        items = (materials.slice(offset, limit) || []).map do |m|
          t = m.texture
          {
            'name' => m.name, 'display_name' => m.display_name,
            'color_rgb' => [m.color.red, m.color.green, m.color.blue],
            'alpha' => m.alpha,
            'texture' => t ? {
              'filename' => t.filename,
              'width_px' => t.image_width, 'height_px' => t.image_height,
              'width_mm' => t.width.to_f * 25.4,
              'height_mm' => t.height.to_f * 25.4
            } : nil
          }
        end
        { 'total' => materials.length, 'offset' => offset, 'items' => items }
      end
    end
  end
end

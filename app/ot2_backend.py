"""Compatibility fix for modern OT-2 fixed-trash commands."""
import ot_api
from pylabrobot.liquid_handling import OpentronsOT2Backend as BaseBackend
from pylabrobot.resources import Trash


class OpentronsOT2Backend(BaseBackend):
    async def drop_tips(self, ops, use_channels):
        # Upstream uses a lexical version comparison: "26.6.0" < "7.1.0".
        # Compare numeric components so current robots use fixedTrash.
        version = tuple(int(p) for p in self.ot_api_version.split(".")[:3])
        if len(ops) == 1 and isinstance(ops[0].resource, Trash) and version >= (7, 1, 0):
            pipette_id = self._get_drop_pipette(ops)
            offset = ops[0].offset
            ot_api.lh.move_to_addressable_area_for_drop_tip(
                pipette_id=pipette_id, offset_x=offset.x,
                offset_y=offset.y, offset_z=offset.z + 10,
            )
            ot_api.lh.drop_tip_in_place(pipette_id=pipette_id)
            self._set_tip_state(pipette_id, False)
            return
        await super().drop_tips(ops, use_channels)

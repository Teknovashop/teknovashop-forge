from __future__ import annotations

import math
import trimesh

from models._helpers import difference, union


def _box(extents, center):
    mesh = trimesh.creation.box(extents=tuple(float(x) for x in extents))
    mesh.apply_translation(tuple(float(x) for x in center))
    return mesh


def _concat(*parts):
    return trimesh.util.concatenate([p for p in parts if p is not None])


def build_vesa_shelf_adapter(p):
    width=float(p.get("width",180)); height=float(p.get("height",120)); depth=float(p.get("depth",65)); thickness=float(p.get("thickness",5))
    vesa=float(p.get("vesa",100)); hole_d=float(p.get("hole_d",5))
    back=_box((width,thickness,height),(0,0,height/2))
    cutters=[]
    for sx in (-1, 1):
        for sz in (-1, 1):
            hole=trimesh.creation.cylinder(radius=hole_d/2,height=thickness*2.4,sections=48)
            hole.apply_transform(trimesh.transformations.rotation_matrix(math.pi/2,[1,0,0]))
            hole.apply_translation((sx*vesa/2,0,height/2 + sz*vesa/2))
            cutters.append(hole)
    back=difference(back, union(cutters))
    shelf=_box((width,depth,thickness),(0,-depth/2,thickness/2))
    lip=_box((width,thickness,20),(0,-depth+thickness/2,10))
    return _concat(back,shelf,lip)


def build_universal_wall_mount(p):
    width=float(p.get("width",130)); height=float(p.get("height",90)); depth=float(p.get("depth",55)); wall=float(p.get("wall",4))
    back=_box((width,wall,height),(0,0,height/2))
    base=_box((width,depth,wall),(0,-depth/2,wall/2))
    rails=_box((width*0.65,wall*2,height*0.2),(0,-wall,height*0.65))
    return _concat(back,base,rails)


def build_multipattern_transition_plate(p):
    width=float(p.get("width",180)); height=float(p.get("height",140)); thickness=float(p.get("thickness",5))
    pattern_a=float(p.get("pattern_a",75)); pattern_b=float(p.get("pattern_b",100)); hole_d=float(p.get("hole_d",5))
    plate=_box((width,height,thickness),(0,0,thickness/2))
    cutters=[]
    for pattern in (pattern_a, pattern_b):
        for sx in (-1, 1):
            for sy in (-1, 1):
                hole=trimesh.creation.cylinder(radius=hole_d/2,height=thickness*2.4,sections=48)
                hole.apply_translation((sx*pattern/2, sy*pattern/2, thickness/2))
                cutters.append(hole)
    return difference(plate, union(cutters))


def build_monitor_riser(p):
    width=float(p.get("width",420)); depth=float(p.get("depth",210)); height=float(p.get("height",85)); wall=float(p.get("wall",5))
    top=_box((width,depth,wall),(0,0,height-wall/2))
    left=_box((wall,depth,height),(-width/2+wall/2,0,height/2))
    right=_box((wall,depth,height),(width/2-wall/2,0,height/2))
    brace=_box((width*0.45,wall,height*0.45),(0,depth/2-wall/2,height*0.225))
    return _concat(top,left,right,brace)


def build_tablet_angle_stand(p):
    width=float(p.get("width",170)); depth=float(p.get("depth",145)); back_h=float(p.get("back_h",125)); wall=float(p.get("wall",4)); angle=float(p.get("angle_deg",62))
    base=_box((width,depth,wall),(0,0,wall/2))
    back=_box((width,wall,back_h),(0,depth*0.18,back_h/2))
    back.apply_transform(trimesh.transformations.rotation_matrix(math.radians(90-angle),[1,0,0]))
    lip=_box((width,wall*2,18),(0,-depth/2+wall,9))
    return _concat(base,back,lip)


def build_microphone_desk_adapter(p):
    base_d=float(p.get("base_d",72)); stem_h=float(p.get("stem_h",55)); stem_d=float(p.get("stem_d",22)); collar_d=float(p.get("collar_d",34))
    base=trimesh.creation.cylinder(radius=base_d/2,height=6,sections=56); base.apply_translation((0,0,3))
    stem=trimesh.creation.cylinder(radius=stem_d/2,height=stem_h,sections=48); stem.apply_translation((0,0,6+stem_h/2))
    collar=trimesh.creation.cylinder(radius=collar_d/2,height=10,sections=48); collar.apply_translation((0,0,6+stem_h+5))
    return _concat(base,stem,collar)


def build_broom_tool_holder(p):
    width=float(p.get("width",140)); height=float(p.get("height",60)); depth=float(p.get("depth",48)); grips=int(round(float(p.get("grips",3))))
    grips=max(2,min(grips,6))
    back=_box((width,5,height),(0,0,height/2))
    parts=[back]
    step=width/(grips+1)
    for i in range(grips):
        x=-width/2+(i+1)*step
        parts.append(_box((12,depth,10),(x,-depth/2,height*0.55)))
    return _concat(*parts)


def build_controller_wall_mount(p):
    width=float(p.get("width",100)); back_h=float(p.get("back_h",85)); arm_depth=float(p.get("arm_depth",75)); wall=float(p.get("wall",5))
    back=_box((width,wall,back_h),(0,0,back_h/2))
    left=_box((wall*2,arm_depth,wall*2),(-width*0.28,-arm_depth/2,back_h*0.35))
    right=_box((wall*2,arm_depth,wall*2),(width*0.28,-arm_depth/2,back_h*0.35))
    return _concat(back,left,right)


def build_speaker_wall_mount(p):
    width=float(p.get("width",120)); depth=float(p.get("depth",115)); back_h=float(p.get("back_h",95)); wall=float(p.get("wall",5))
    back=_box((width,wall,back_h),(0,0,back_h/2))
    shelf=_box((width,depth,wall),(0,-depth/2,wall/2))
    lip=_box((width,wall*1.5,18),(0,-depth+wall,9))
    return _concat(back,shelf,lip)


def build_wall_cable_clip(p):
    length=float(p.get("length",36)); width=float(p.get("width",22)); height=float(p.get("height",18)); gap=float(p.get("gap",8))
    base=_box((length,width,3),(0,0,1.5))
    left=_box((4,width,height),(-gap/2-2,0,3+height/2))
    right=_box((4,width,height),(gap/2+2,0,3+height/2))
    return _concat(base,left,right)


def build_light_clamp_block(p):
    length=float(p.get("length",70)); width=float(p.get("width",45)); height=float(p.get("height",28)); jaw=float(p.get("jaw",12))
    base=_box((length,width,8),(0,0,4))
    left=_box((jaw,width,height),(-length/2+jaw/2,0,8+height/2))
    right=_box((jaw,width,height),(length/2-jaw/2,0,8+height/2))
    bridge=_box((length*0.45,width*0.35,6),(0,0,8+height+3))
    return _concat(base,left,right,bridge)


def build_cutting_guide(p):
    length=float(p.get("length",240)); width=float(p.get("width",55)); height=float(p.get("height",28)); fence=float(p.get("fence",8))
    base=_box((length,width,5),(0,0,2.5))
    rail=_box((length,fence,height),(0,width/2-fence/2,5+height/2))
    nose=_box((fence,width,height*0.45),(-length/2+fence/2,0,5+height*0.225))
    return _concat(base,rail,nose)


def build_parametric_spacer(p):
    length=float(p.get("length",70)); width=float(p.get("width",45)); thickness=float(p.get("thickness",8)); step=float(p.get("step",4))
    base=_box((length,width,thickness),(0,0,thickness/2))
    ridge=_box((length*0.65,width*0.35,step),(0,0,thickness+step/2))
    return _concat(base,ridge)


def build_bit_key_organizer(p):
    width=float(p.get("width",160)); depth=float(p.get("depth",65)); height=float(p.get("height",25)); bays=int(round(float(p.get("bays",8))))
    bays=max(4,min(bays,14))
    base=_box((width,depth,5),(0,0,2.5))
    parts=[base]
    step=width/(bays+1)
    for i in range(bays):
        x=-width/2+(i+1)*step
        parts.append(_box((4,depth*0.72,height),(x,0,5+height/2)))
    return _concat(*parts)


def build_parametric_lidded_box(p):
    length=float(p.get("length",150)); width=float(p.get("width",95)); height=float(p.get("height",55)); wall=float(p.get("wall",3)); lid=float(p.get("lid",3))
    base=_box((length,width,wall),(0,0,wall/2))
    left=_box((wall,width,height),(-length/2+wall/2,0,height/2))
    right=_box((wall,width,height),(length/2-wall/2,0,height/2))
    front=_box((length,wall,height),(0,-width/2+wall/2,height/2))
    back=_box((length,wall,height),(0,width/2-wall/2,height/2))
    top=_box((length+wall*2,width+wall*2,lid),(0,0,height+lid*1.5))
    return _concat(base,left,right,front,back,top)


def build_stackable_box(p):
    length=float(p.get("length",140)); width=float(p.get("width",90)); height=float(p.get("height",60)); wall=float(p.get("wall",3)); rim=float(p.get("rim",6))
    base=_box((length,width,wall),(0,0,wall/2))
    walls=[_box((wall,width,height),(-length/2+wall/2,0,height/2)),_box((wall,width,height),(length/2-wall/2,0,height/2)),_box((length,wall,height),(0,-width/2+wall/2,height/2)),_box((length,wall,height),(0,width/2-wall/2,height/2))]
    rim_box=_box((length+rim,width+rim,wall),(0,0,height-wall/2))
    return _concat(base,*walls,rim_box)


def build_modular_tray(p):
    length=float(p.get("length",180)); width=float(p.get("width",120)); height=float(p.get("height",28)); wall=float(p.get("wall",3)); divider=float(p.get("divider",4))
    base=_box((length,width,wall),(0,0,wall/2))
    sides=[_box((wall,width,height),(-length/2+wall/2,0,height/2)),_box((wall,width,height),(length/2-wall/2,0,height/2)),_box((length,wall,height),(0,-width/2+wall/2,height/2)),_box((length,wall,height),(0,width/2-wall/2,height/2))]
    div=_box((divider,width-wall*2,height*0.65),(0,0,height*0.325))
    return _concat(base,*sides,div)


def build_desk_organizer(p):
    width=float(p.get("width",180)); depth=float(p.get("depth",100)); height=float(p.get("height",75)); bays=int(round(float(p.get("bays",4))))
    bays=max(2,min(bays,8))
    base=_box((width,depth,5),(0,0,2.5))
    back=_box((width,5,height),(0,depth/2-2.5,height/2))
    parts=[base,back]
    step=width/bays
    for i in range(1,bays):
        x=-width/2+i*step
        parts.append(_box((4,depth,height*0.72),(x,0,height*0.36)))
    return _concat(*parts)


def build_modular_pen_holder(p):
    outer_d=float(p.get("outer_d",85)); height=float(p.get("height",105)); wall=float(p.get("wall",4)); cells=int(round(float(p.get("cells",3))))
    cells=max(2,min(cells,5))
    base=trimesh.creation.cylinder(radius=outer_d/2,height=wall,sections=64); base.apply_translation((0,0,wall/2))
    parts=[base]
    radius=outer_d*0.22
    for i in range(cells):
        a=2*math.pi*i/cells
        cup=trimesh.creation.cylinder(radius=radius,height=height,sections=48)
        cup.apply_translation((math.cos(a)*outer_d*0.2,math.sin(a)*outer_d*0.2,wall+height/2))
        parts.append(cup)
    return _concat(*parts)


def build_hardware_box(p):
    length=float(p.get("length",190)); width=float(p.get("width",125)); height=float(p.get("height",45)); cells=int(round(float(p.get("cells",6))))
    cells=max(3,min(cells,10))
    base=_box((length,width,5),(0,0,2.5))
    outer=[_box((5,width,height),(-length/2+2.5,0,height/2)),_box((5,width,height),(length/2-2.5,0,height/2)),_box((length,5,height),(0,-width/2+2.5,height/2)),_box((length,5,height),(0,width/2-2.5,height/2))]
    parts=[base,*outer]
    step=length/cells
    for i in range(1,cells):
        x=-length/2+i*step
        parts.append(_box((3,width-10,height*0.72),(x,0,height*0.36)))
    return _concat(*parts)


def build_accessory_rack(p):
    width=float(p.get("width",220)); depth=float(p.get("depth",80)); height=float(p.get("height",110)); levels=int(round(float(p.get("levels",3))))
    levels=max(2,min(levels,5))
    left=_box((5,depth,height),(-width/2+2.5,0,height/2))
    right=_box((5,depth,height),(width/2-2.5,0,height/2))
    parts=[left,right]
    for i in range(levels):
        z=(i+1)*height/(levels+1)
        parts.append(_box((width,depth,4),(0,0,z)))
    return _concat(*parts)


def build_inset_label(p):
    length=float(p.get("length",90)); width=float(p.get("width",32)); thickness=float(p.get("thickness",4)); tab=float(p.get("tab",12))
    plate=_box((length,width,thickness),(0,0,thickness/2))
    t=_box((tab,width*0.45,thickness*1.5),(length/2+tab/2,0,thickness*0.75))
    return _concat(plate,t)


def build_sd_card_organizer(p):
    width=float(p.get("width",120)); depth=float(p.get("depth",70)); height=float(p.get("height",28)); slots=int(round(float(p.get("slots",8))))
    slots=max(4,min(slots,16))
    base=_box((width,depth,5),(0,0,2.5))
    parts=[base]
    step=width/(slots+1)
    for i in range(slots):
        x=-width/2+(i+1)*step
        parts.append(_box((3,depth*0.65,height),(x,0,5+height/2)))
    return _concat(*parts)


def build_cable_reel(p):
    outer_d=float(p.get("outer_d",95)); core_d=float(p.get("core_d",35)); width=float(p.get("width",38)); flange=float(p.get("flange",4))
    core=trimesh.creation.cylinder(radius=core_d/2,height=width,sections=64); core.apply_translation((0,0,width/2))
    a=trimesh.creation.cylinder(radius=outer_d/2,height=flange,sections=64); a.apply_translation((0,0,flange/2))
    b=trimesh.creation.cylinder(radius=outer_d/2,height=flange,sections=64); b.apply_translation((0,0,width-flange/2))
    return _concat(core,a,b)

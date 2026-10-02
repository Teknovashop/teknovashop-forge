from __future__ import annotations
import math
import trimesh


def _box(extents, center):
    mesh = trimesh.creation.box(extents=tuple(float(x) for x in extents))
    mesh.apply_translation(tuple(float(x) for x in center))
    return mesh


def _concat(*parts):
    return trimesh.util.concatenate([p for p in parts if p is not None])


def build_vesa_offset_adapter(p):
    width=float(p.get("width",150)); height=float(p.get("height",120)); thickness=float(p.get("thickness",5)); offset=float(p.get("offset",35))
    plate=_box((width,height,thickness),(0,0,thickness/2))
    bridge=_box((max(20,abs(offset)+20),height*0.28,thickness*1.6),(offset/2,0,thickness*0.8))
    return _concat(plate,bridge)


def build_under_desk_mount(p):
    width=float(p.get("width",130)); depth=float(p.get("depth",90)); height=float(p.get("height",55)); wall=float(p.get("wall",4))
    base=_box((width,depth,wall),(0,0,wall/2))
    back=_box((width,wall,height),(0,depth/2-wall/2,height/2))
    lip=_box((width,wall*1.2,height*0.35),(0,-depth/2+wall/2,height*0.175))
    return _concat(base,back,lip)


def build_perforated_mount_plate(p):
    width=float(p.get("width",150)); height=float(p.get("height",100)); thickness=float(p.get("thickness",5)); boss=float(p.get("boss",12))
    plate=_box((width,height,thickness),(0,0,thickness/2))
    b1=trimesh.creation.cylinder(radius=boss/2,height=thickness*1.8,sections=36); b1.apply_translation((-width*0.3,0,thickness*0.9))
    b2=b1.copy(); b2.apply_translation((width*0.6,0,0))
    return _concat(plate,b1,b2)


def build_circular_pattern_adapter(p):
    outer_d=float(p.get("outer_d",100)); hub_d=float(p.get("hub_d",36)); thickness=float(p.get("thickness",6)); boss_h=float(p.get("boss_h",8))
    disc=trimesh.creation.cylinder(radius=outer_d/2,height=thickness,sections=72); disc.apply_translation((0,0,thickness/2))
    hub=trimesh.creation.cylinder(radius=hub_d/2,height=boss_h,sections=48); hub.apply_translation((0,0,thickness+boss_h/2))
    return _concat(disc,hub)


def build_phone_landscape_stand(p):
    width=float(p.get("width",150)); depth=float(p.get("depth",85)); back_h=float(p.get("back_h",70)); wall=float(p.get("wall",4)); lip=float(p.get("lip",12))
    base=_box((width,depth,wall),(0,0,wall/2))
    back=_box((width,wall,back_h),(0,depth*0.25,back_h/2))
    front=_box((width,wall,lip),(0,-depth/2+wall/2,lip/2))
    return _concat(base,back,front)


def build_smartwatch_stand(p):
    base_d=float(p.get("base_d",80)); stem_h=float(p.get("stem_h",95)); stem_d=float(p.get("stem_d",18)); cradle_d=float(p.get("cradle_d",48))
    base=trimesh.creation.cylinder(radius=base_d/2,height=5,sections=64); base.apply_translation((0,0,2.5))
    stem=trimesh.creation.cylinder(radius=stem_d/2,height=stem_h,sections=48); stem.apply_translation((0,0,5+stem_h/2))
    cradle=trimesh.creation.cylinder(radius=cradle_d/2,height=7,sections=64); cradle.apply_translation((0,0,5+stem_h+3.5))
    return _concat(base,stem,cradle)


def build_cable_comb(p):
    length=float(p.get("length",90)); width=float(p.get("width",22)); height=float(p.get("height",14)); teeth=int(round(float(p.get("teeth",6))))
    teeth=max(2,min(teeth,12))
    base=_box((length,width,4),(0,0,2))
    parts=[base]
    step=length/(teeth+1)
    for i in range(teeth):
        x=-length/2+(i+1)*step
        parts.append(_box((3,width,height),(x,0,4+height/2)))
    return _concat(*parts)


def build_charger_retainer(p):
    width=float(p.get("width",70)); depth=float(p.get("depth",45)); height=float(p.get("height",28)); wall=float(p.get("wall",3))
    base=_box((width,depth,wall),(0,0,wall/2))
    left=_box((wall,depth,height),(-width/2+wall/2,0,height/2))
    right=_box((wall,depth,height),(width/2-wall/2,0,height/2))
    back=_box((width,wall,height),(0,depth/2-wall/2,height/2))
    return _concat(base,left,right,back)


def build_zip_tie_anchor(p):
    length=float(p.get("length",32)); width=float(p.get("width",22)); height=float(p.get("height",9)); bridge=float(p.get("bridge",8))
    base=_box((length,width,3),(0,0,1.5))
    a=_box((bridge,4,height),(-length*0.22,0,3+height/2))
    b=_box((bridge,4,height),(length*0.22,0,3+height/2))
    top=_box((length*0.55,4,3),(0,0,3+height+1.5))
    return _concat(base,a,b,top)


def build_nvme_caddy(p):
    length=float(p.get("length",115)); width=float(p.get("width",38)); height=float(p.get("height",18)); wall=float(p.get("wall",3))
    base=_box((length,width,wall),(0,0,wall/2))
    left=_box((length,wall,height),(0,-width/2+wall/2,height/2))
    right=_box((length,wall,height),(0,width/2-wall/2,height/2))
    stop=_box((wall,width,height),(length/2-wall/2,0,height/2))
    return _concat(base,left,right,stop)


def build_power_supply_mount(p):
    width=float(p.get("width",115)); depth=float(p.get("depth",55)); height=float(p.get("height",40)); wall=float(p.get("wall",4)); strap=float(p.get("strap",16))
    base=_box((width,depth,wall),(0,0,wall/2))
    left=_box((wall,depth,height),(-width/2+wall/2,0,height/2))
    right=_box((wall,depth,height),(width/2-wall/2,0,height/2))
    bridge=_box((strap,depth,wall),(0,0,height-wall/2))
    return _concat(base,left,right,bridge)


def build_cold_shoe_adapter(p):
    length=float(p.get("length",30)); width=float(p.get("width",22)); base_t=float(p.get("base_t",4)); post_h=float(p.get("post_h",12))
    base=_box((length,width,base_t),(0,0,base_t/2))
    neck=_box((length*0.58,width*0.55,post_h),(0,0,base_t+post_h/2))
    cap=_box((length*0.78,width*0.72,3),(0,0,base_t+post_h+1.5))
    return _concat(base,neck,cap)


def build_led_light_mount(p):
    width=float(p.get("width",65)); depth=float(p.get("depth",48)); height=float(p.get("height",45)); wall=float(p.get("wall",4)); tilt=float(p.get("tilt_deg",15))
    base=_box((width,depth,wall),(0,0,wall/2))
    stem=_box((wall*2,depth*0.4,height),(0,0,height/2))
    plate=_box((width*0.72,depth*0.55,wall),(0,math.sin(math.radians(tilt))*4,height))
    plate.apply_transform(trimesh.transformations.rotation_matrix(math.radians(tilt),[1,0,0]))
    return _concat(base,stem,plate)


def build_audio_interface_mount(p):
    width=float(p.get("width",165)); depth=float(p.get("depth",115)); height=float(p.get("height",35)); wall=float(p.get("wall",4))
    base=_box((width,depth,wall),(0,0,wall/2))
    l=_box((wall,depth,height),(-width/2+wall/2,0,height/2))
    r=_box((wall,depth,height),(width/2-wall/2,0,height/2))
    return _concat(base,l,r)


def build_battery_card_holder(p):
    width=float(p.get("width",120)); depth=float(p.get("depth",65)); height=float(p.get("height",32)); bays=int(round(float(p.get("bays",4))))
    bays=max(2,min(bays,8))
    base=_box((width,depth,4),(0,0,2))
    parts=[base]
    step=width/bays
    for i in range(bays+1):
        x=-width/2+i*step
        parts.append(_box((3,depth,height),(x,0,4+height/2)))
    return _concat(*parts)


def build_double_wall_hook(p):
    base_w=float(p.get("base_w",75)); base_h=float(p.get("base_h",60)); hook_d=float(p.get("hook_d",35)); hook_t=float(p.get("hook_t",8))
    base=_box((base_w,4,base_h),(0,0,base_h/2))
    parts=[base]
    for x in (-base_w*0.23,base_w*0.23):
        arm=_box((hook_t,hook_d,hook_t),(x,-hook_d/2,base_h*0.42))
        tip=_box((hook_t,hook_t,hook_t*2),(x,-hook_d+hook_t/2,base_h*0.42+hook_t/2))
        parts.extend([arm,tip])
    return _concat(*parts)


def build_compact_wall_shelf(p):
    width=float(p.get("width",180)); depth=float(p.get("depth",110)); back_h=float(p.get("back_h",65)); wall=float(p.get("wall",4))
    shelf=_box((width,depth,wall),(0,0,wall/2))
    back=_box((width,wall,back_h),(0,depth/2-wall/2,back_h/2))
    l=_box((wall,depth*0.6,back_h*0.55),(-width/2+wall/2,depth*0.15,back_h*0.275))
    r=l.copy(); r.apply_translation((width-wall,0,0))
    return _concat(shelf,back,l,r)


def build_tool_holder(p):
    width=float(p.get("width",160)); height=float(p.get("height",60)); depth=float(p.get("depth",48)); slots=int(round(float(p.get("slots",5))))
    slots=max(2,min(slots,10))
    back=_box((width,4,height),(0,0,height/2))
    rail=_box((width,depth,4),(0,-depth/2,4/2))
    parts=[back,rail]
    step=width/(slots+1)
    for i in range(slots):
        x=-width/2+(i+1)*step
        parts.append(_box((4,depth,height*0.45),(x,-depth/2,height*0.225)))
    return _concat(*parts)

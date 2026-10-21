// A deterministic visualization of an unvalidated design candidate.
// The keyframed supports are NOT a contact, kinematics or force solver.
import * as THREE from 'three';

const W=1920,H=1080;
const scene=new THREE.Scene();
scene.background=new THREE.Color('#edf0f0');
scene.fog=new THREE.Fog('#edf0f0',8,20);
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(window.devicePixelRatio);
renderer.setSize(innerWidth,innerHeight);
renderer.shadowMap.enabled=true;
renderer.shadowMap.type=THREE.PCFSoftShadowMap;
renderer.toneMapping=THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure=1.12;
document.body.prepend(renderer.domElement);
const camera=new THREE.OrthographicCamera(-2.4,2.4,1.35,-1.35,.01,35);
const ambient=new THREE.HemisphereLight(0xe6f3ff,0x7c8587,2.2);scene.add(ambient);
const key=new THREE.DirectionalLight(0xfff8ed,4.0);key.position.set(2.5,5,3.5);key.castShadow=true;
key.shadow.mapSize.set(2048,2048);key.shadow.camera.left=-4;key.shadow.camera.right=4;key.shadow.camera.top=4;key.shadow.camera.bottom=-4;key.shadow.camera.near=.1;key.shadow.camera.far=12;key.shadow.bias=-.00025;key.shadow.normalBias=.016;scene.add(key);
const fill=new THREE.DirectionalLight(0xd4e7f7,1.8);fill.position.set(-3,3,-2);scene.add(fill);
const rim=new THREE.DirectionalLight(0xffffff,1.4);rim.position.set(-2,3,4);scene.add(rim);

// A small synthetic studio environment supplies broad reflections to metals.
const env=new THREE.Scene();env.background=new THREE.Color(0xbcc5ca);
for(const [x,y,z,sx,sy,sz,color] of [[0,4,0,7,.05,5,0xffffff],[-4,1,0,.05,4,5,0xe7edf6],[0,2,-4,7,3,.05,0xcbd7e1],[3,2,2,2,3,.05,0xffffff]]){
 const p=new THREE.Mesh(new THREE.BoxGeometry(sx,sy,sz),new THREE.MeshBasicMaterial({color}));p.position.set(x,y,z);env.add(p);
}
const pmrem=new THREE.PMREMGenerator(renderer);scene.environment=pmrem.fromScene(env,.04).texture;pmrem.dispose();

const mat={
 white:new THREE.MeshPhysicalMaterial({color:0xe0e6e3,roughness:.37,metalness:.30,clearcoat:.35}),
 teal:new THREE.MeshPhysicalMaterial({color:0x145661,roughness:.30,metalness:.5,clearcoat:.45}),
 dark:new THREE.MeshStandardMaterial({color:0x25343c,roughness:.43,metalness:.6}),
 steel:new THREE.MeshStandardMaterial({color:0xaab6bd,roughness:.25,metalness:.87}),
 rubber:new THREE.MeshStandardMaterial({color:0x1c2429,roughness:.85,metalness:.03}),
 tread:new THREE.MeshStandardMaterial({color:0x303a3d,roughness:.75,metalness:.06}),
 cushion:new THREE.MeshPhysicalMaterial({color:0x313c40,roughness:.88,metalness:0,clearcoat:.08}),
 orange:new THREE.MeshPhysicalMaterial({color:0xcb8137,roughness:.4,metalness:.5}),
 black:new THREE.MeshStandardMaterial({color:0x111e25,roughness:.58,metalness:.3}),
 red:new THREE.MeshStandardMaterial({color:0xcb4d41,roughness:.4}),
 green:new THREE.MeshStandardMaterial({color:0x56c7a4,roughness:.4,emissive:0x196850,emissiveIntensity:.35}),
 belt:new THREE.MeshStandardMaterial({color:0x273139,roughness:1}),
 floor:new THREE.MeshStandardMaterial({color:0xe7ecea,roughness:.92,metalness:.02}),
 step:new THREE.MeshStandardMaterial({color:0xbcc6c7,roughness:.9,metalness:0}),
};

const root=new THREE.Group();scene.add(root);
const hardware=new THREE.Group();root.add(hardware);
const trackGroups=[];
function mesh(geometry,material,parent=hardware){const o=new THREE.Mesh(geometry,material);o.castShadow=true;o.receiveShadow=true;parent.add(o);return o;}
function box(parent,x,y,z,sx,sy,sz,material,round=.02){
 const shape=new THREE.Shape();const a=sx/2,b=sy/2,r=Math.min(round,a*.8,b*.8);
 shape.moveTo(-a+r,-b);shape.lineTo(a-r,-b);shape.quadraticCurveTo(a,-b,a,-b+r);shape.lineTo(a,b-r);shape.quadraticCurveTo(a,b,a-r,b);shape.lineTo(-a+r,b);shape.quadraticCurveTo(-a,b,-a,b-r);shape.lineTo(-a,-b+r);shape.quadraticCurveTo(-a,-b,-a+r,-b);
 const geo=new THREE.ExtrudeGeometry(shape,{depth:sz,bevelEnabled:round>0,bevelSize:Math.min(round*.25,.006),bevelThickness:Math.min(round*.25,.006),bevelSegments:2,steps:1,curveSegments:5});geo.translate(0,0,-sz/2);
 const o=mesh(geo,material,parent);o.position.set(x,y,z);return o;
}
function cyl(parent,x,y,z,r,len,material,axis='z'){
 const o=mesh(new THREE.CylinderGeometry(r,r,len,24),material,parent);if(axis==='z')o.rotation.x=Math.PI/2;if(axis==='x')o.rotation.z=Math.PI/2;o.position.set(x,y,z);return o;
}
function beam(parent,a,b,r,material){const v=new THREE.Vector3(...a),w=new THREE.Vector3(...b),d=w.clone().sub(v);const o=mesh(new THREE.CylinderGeometry(r,r,d.length(),16),material,parent);o.position.copy(v.add(w).multiplyScalar(.5));o.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),d.normalize());return o;}
function capsule(shape,a,r,cy){shape.moveTo(-a,cy-r);shape.lineTo(a,cy-r);shape.absarc(a,cy,r,-Math.PI/2,Math.PI/2,false);shape.lineTo(-a,cy+r);shape.absarc(-a,cy,r,Math.PI/2,Math.PI*1.5,false);shape.closePath();}
function track(z){
 const g=new THREE.Group();g.position.z=z;hardware.add(g);trackGroups.push(g);
 const a=.385,r=.115,cy=.126,width=.16;
 const shape=new THREE.Shape();capsule(shape,a,r,cy);const hole=new THREE.Path();capsule(hole,a,.087,cy);shape.holes.push(hole);
 const geo=new THREE.ExtrudeGeometry(shape,{depth:width,bevelEnabled:false,curveSegments:24});geo.translate(0,0,-width/2);mesh(geo,mat.rubber,g);
 for(const x of [-a,-.20,0,.20,a]){
  const rad=Math.abs(x)>.3?.083:.073;
  cyl(g,x,cy,0,rad,.142,mat.dark);cyl(g,x,cy,Math.sign(z)*.084,rad*.69,.015,mat.steel);cyl(g,x,cy,Math.sign(z)*.096,.020,.018,mat.dark);
  for(let k=0;k<5;k++){const q=k*Math.PI*2/5;cyl(g,x+rad*.43*Math.cos(q),cy+rad*.43*Math.sin(q),Math.sign(z)*.098,.005,.01,mat.black);}
 }
 const straight=2*a,L=2*straight+2*Math.PI*r;const treads=[];
 function pos(s){s=((s%L)+L)%L;if(s<straight)return[-a+s,cy-r,0];s-=straight;if(s<Math.PI*r){const ang=-Math.PI/2+s/r;return[a+r*Math.cos(ang),cy+r*Math.sin(ang),ang+Math.PI/2];}s-=Math.PI*r;if(s<straight)return[a-s,cy+r,Math.PI];s-=straight;const ang=Math.PI/2+s/r;return[-a+r*Math.cos(ang),cy+r*Math.sin(ang),ang+Math.PI/2];}
 for(let i=0;i<46;i++){const o=mesh(new THREE.BoxGeometry(.035,.018,.177),mat.tread,g);treads.push(o);}
 g.userData.animate=(distance)=>{for(let i=0;i<treads.length;i++){const [x,y,angle]=pos(i*L/treads.length+distance);treads[i].position.set(x,y,0);treads[i].rotation.z=angle;}};
 g.userData.animate(0);
 beam(g,[-.37,.157,0],[.37,.157,0],.014,mat.steel);
}
track(.27);track(-.27);

// Carrying frame, low battery shell, side covers, controls and service details.
box(hardware,0,.285,0,.83,.13,.47,mat.dark);
for(const z of [-.205,.205])beam(hardware,[-.40,.29,z],[.4,.29,z],.023,mat.steel);
for(const x of [-.33,.32])beam(hardware,[x,.28,-.27],[x,.28,.27],.026,mat.dark);
box(hardware,-.11,.365,0,.57,.19,.39,mat.teal,.045);
box(hardware,.26,.34,0,.19,.13,.42,mat.white,.027);
for(const z of [-.227,.227]){
 box(hardware,-.12,.407,z,.52,.071,.027,mat.white,.015);
 for(let i=0;i<5;i++)box(hardware,-.26+i*.045,.404,z+Math.sign(z)*.018,.022,.006,.006,mat.dark,.001);
 for(const x of [-.355,.115])cyl(hardware,x,.405,z+Math.sign(z)*.024,.008,.008,mat.steel);
}
box(hardware,-.30,.34,.246,.05,.07,.023,mat.black,.005);cyl(hardware,-.30,.35,.264,.012,.01,mat.green);
for(const z of [-.15,.15]){
 box(hardware,.372,.345,z,.02,.03,.05,mat.black,.004);
 box(hardware,.385,.347,z,.008,.012,.03,mat.white,.002);
}

const cradle=new THREE.Group();cradle.position.set(-.03,.54,0);hardware.add(cradle);
beam(hardware,[-.18,.39,-.15],[-.03,.54,-.15],.025,mat.steel);
beam(hardware,[-.18,.39,.15],[-.03,.54,.15],.025,mat.steel);
cyl(hardware,-.03,.54,0,.055,.39,mat.orange);
for(const z of [-.208,.208])cyl(hardware,-.03,.54,z,.035,.018,mat.dark);
const seat=new THREE.Group();cradle.add(seat);
box(seat,.00,.040,0,.48,.06,.45,mat.dark,.014);
box(seat,.018,.093,0,.48,.075,.465,mat.cushion,.035);
// Back frame is tilted slightly for a supported seated posture.
for(const z of [-.211,.211])beam(seat,[-.22,.045,z],[-.295,.73,z],.018,mat.steel);
const back=box(seat,-.264,.455,0,.083,.59,.445,mat.cushion,.038);back.rotation.z=-.10;
box(seat,-.268,.785,0,.086,.18,.245,mat.cushion,.033);
for(const z of [-.279,.279]){
 beam(seat,[-.17,.035,z],[-.16,.337,z],.017,mat.dark);
 box(seat,.025,.352,z,.43,.055,.080,mat.cushion,.02);
}
// An extra support pad on the user's right (-z) side, intentionally asymmetric.
box(seat,-.17,.425,-.235,.20,.23,.06,mat.cushion,.026);
// Left (+z) joystick and reachable emergency stop, with a small display.
const controls=box(seat,.257,.365,.289,.15,.046,.12,mat.dark,.02);controls.rotation.z=-.08;
const display=box(seat,.258,.391,.269,.070,.005,.053,mat.black,.004);display.rotation.z=-.08;
box(seat,.26,.396,.266,.052,.004,.035,mat.teal,.002);
cyl(seat,.276,.423,.322,.010,.055,mat.steel,'y');
const joystick=mesh(new THREE.SphereGeometry(.022,20,12),mat.rubber,seat);joystick.position.set(.276,.456,.322);
cyl(seat,.214,.403,.323,.018,.012,mat.red,'y');
// Foot supports with heel stops and straps.
for(const z of [-.138,.138]){
 beam(seat,[.20,.02,z],[.36,-.245,z],.017,mat.dark);
 const foot=box(seat,.444,-.260,z,.25,.027,.20,mat.dark,.013);foot.rotation.z=.02;
 box(seat,.337,-.23,z,.023,.07,.20,mat.dark,.007);
 box(seat,.448,-.235,z,.04,.025,.19,mat.belt,.004);
 for(let i=0;i<4;i++)box(seat,.38+i*.042,-.241,z,.012,.008,.17,mat.rubber,.001);
}
// Lap belt kept open in this unoccupied appearance concept.
for(const z of [-.19,.19]){const belt=box(seat,-.01,.143,z,.13,.018,.055,mat.belt,.005);belt.rotation.y=Math.sign(z)*.35;}
box(seat,.03,.15,.125,.034,.018,.036,mat.steel,.004);

// Two simple render cylinders show the leveling actuator arrangement.
const actuator=new THREE.Group();hardware.add(actuator);
function rebuildActuator(){for(const c of actuator.children)c.geometry.dispose();actuator.clear();const end=new THREE.Vector3(.16,-.005,0);seat.localToWorld(end);hardware.worldToLocal(end);const start=new THREE.Vector3(.20,.35,0),mid=start.clone().lerp(end,.57);beam(actuator,start.toArray(),mid.toArray(),.026,mat.dark);beam(actuator,mid.toArray(),end.toArray(),.014,mat.steel);cyl(actuator,start.x,start.y,0,.025,.10,mat.steel);}

// Four articulated/telescoping support legs. The artist-defined trajectory
// illustrates a candidate only; lengths and joint closure are not solved.
const legMeshes=[];
function dynamicBar(material,r){const o=mesh(new THREE.CylinderGeometry(r,r,1,16),material,scene);legMeshes.push(o);return o;}
function setBar(o,a,b){const d=b.clone().sub(a);o.position.copy(a).add(b).multiplyScalar(.5);o.scale.y=d.length();o.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),d.normalize());}
const legs=[];
for(const front of [-1,1])for(const side of [-1,1]){
 const upper=dynamicBar(mat.orange,.029),lower=dynamicBar(mat.steel,.020),brace=dynamicBar(mat.dark,.014);
 const joints=[0,1].map(()=>{const o=cyl(scene,0,0,0,.040,.077,mat.dark);legMeshes.push(o);return o;});
 const pad=box(scene,0,0,0,.19,.034,.17,mat.dark,.018);legMeshes.push(pad);
 const shoe=box(scene,0,0,0,.17,.012,.15,mat.rubber,.007);legMeshes.push(shoe);
 legs.push({front,side,upper,lower,brace,joints,pad,shoe});
}
function supportLegs(pose){
 root.updateMatrixWorld(true);
 for(const leg of legs){
  const f=leg.front,s=leg.side;
  const hip=root.localToWorld(new THREE.Vector3(f*.36,.305,s*.365));
  const folded=root.localToWorld(new THREE.Vector3(f*.56,.055,s*.405));
  const foot=folded.clone();
  if(pose.deploy>0){
   let target;
   if(f>0)target=new THREE.Vector3(1.13,.42,s*.47);
   else if(pose.rearSwing<=0)target=new THREE.Vector3(-.34,.020,s*.48);
   else if(pose.rearSwing<.5)target=new THREE.Vector3(THREE.MathUtils.lerp(-.34,.83,pose.rearSwing*2),THREE.MathUtils.lerp(.020,.71,pose.rearSwing*2),s*.48);
   else target=new THREE.Vector3(THREE.MathUtils.lerp(.83,1.16,(pose.rearSwing-.5)*2),THREE.MathUtils.lerp(.71,.42,(pose.rearSwing-.5)*2),s*.48);
   foot.lerp(target,pose.deploy);
  }
  const foldedElbow=root.localToWorld(new THREE.Vector3(f*.47,.25,s*.42));
  const unfolded=hip.clone().lerp(foot,.52);unfolded.y=Math.max(hip.y,foot.y)+.15;unfolded.z=s*.46;
  if(hip.y<.41&&foot.x>.95&&foot.y>.39)unfolded.x=Math.min(unfolded.x,.79);
  const elbow=foldedElbow.lerp(unfolded,pose.deploy);
  setBar(leg.upper,hip,elbow);setBar(leg.lower,elbow,foot);
  const braceStart=hip.clone().lerp(elbow,.28),braceEnd=elbow.clone().lerp(foot,.48);setBar(leg.brace,braceStart,braceEnd);
  leg.joints[0].position.copy(hip);leg.joints[1].position.copy(elbow);
  leg.pad.position.copy(foot);leg.shoe.position.copy(foot);leg.shoe.position.y-=.021;
 }
}

const floor=mesh(new THREE.PlaneGeometry(200,200),mat.floor,scene);floor.rotation.x=-Math.PI/2;floor.position.y=-.011;floor.castShadow=false;
const obstacle=new THREE.Group();scene.add(obstacle);
const block=box(obstacle,2.36,.19,0,2.82,.4,2.05,mat.step,0);
// Keep the upper surface at exactly 0.400 m in the drawing.
block.position.y=.200;block.geometry.computeBoundingBox();
const edge=box(obstacle,.954,.397,0,.009,.008,2.04,mat.white,.001);
for(const z of [-1.026,1.026])box(obstacle,2.36,.18,z,2.78,.005,.005,mat.white,.001);
obstacle.visible=false;

const overlay=document.getElementById('overlay');
const title=document.getElementById('title'),subtitle=document.getElementById('subtitle'),badge=document.getElementById('badge');
const phases=[
 ['整机外观','左手控制 · 右侧支撑 · 履带底盘 · 辅助支腿'],
 ['单手操纵与座椅调平','演示底盘倾斜时，座椅反向转动以保持水平的设计意图。'],
 ['低速接近障碍','这里展示已确认的 400 mm 单级目标；停靠位置与检测方案待定。'],
 ['支腿展开，建立候选支撑','前支腿伸向顶面，后支腿留在下层；接触与锁止尚待求解。'],
 ['抬升底盘，座椅保持水平','四角机构共同抬升的构想；画面不计算执行器受力和稳定裕量。'],
 ['向顶面转移','演示履带落向顶面、后支腿抬起并转移的动作顺序意图。'],
 ['落稳后收回支腿','顶面空间、下降动作和失电保持还需要分别验证。'],
 ['下一步：把动作变成可验证机构','此视频展示候选外观与动作意图，不能作为 400 mm 通过能力的证据。'],
];
const labels=['外观','操纵 / 调平','接近','支撑','抬升','转移','收回'];
document.getElementById('timeline').innerHTML=labels.map((n,i)=>`<div class="step" data-i="${i}">${String(i+1).padStart(2,'0')}　${n}</div>`).join('');
function smooth(v){v=THREE.MathUtils.clamp(v,0,1);return v*v*(3-2*v);}
function range(t,a,b){return smooth((t-a)/(b-a));}
function poseAt(t){
 if(t<3.5)return{x:0,y:0,pitch:0,deploy:0,rearSwing:0,travel:0,phase:0};
 if(t<8.5){const p=Math.sin((t-3.5)/5*Math.PI*2)*THREE.MathUtils.degToRad(7);return{x:0,y:Math.abs(Math.sin(p))*.50,pitch:p,deploy:0,rearSwing:0,travel:0,phase:1};}
 if(t<12)return{x:THREE.MathUtils.lerp(-.3,.30,range(t,8.5,12)),y:0,pitch:0,deploy:0,rearSwing:0,travel:(t-8.5)*.18,phase:2};
 if(t<16)return{x:.30,y:0,pitch:0,deploy:range(t,12,16),rearSwing:0,travel:0,phase:3};
 if(t<20){const v=range(t,16,20),p=Math.sin(v*Math.PI)*.07;return{x:.30,y:.42*v,pitch:p,deploy:1,rearSwing:0,travel:0,phase:4};}
 if(t<26){const v=range(t,20,26);return{x:THREE.MathUtils.lerp(.30,1.65,v),y:.42,pitch:0,deploy:1,rearSwing:range(v,.50,.93),travel:(t-20)*.20,phase:5};}
 if(t<30)return{x:1.65,y:THREE.MathUtils.lerp(.42,.40,range(t,26,27.4)),pitch:0,deploy:1-range(t,27.4,30),rearSwing:1,travel:0,phase:6};
 return{x:1.65,y:.40,pitch:0,deploy:0,rearSwing:1,travel:0,phase:7};
}

function project(point){const p=new THREE.Vector3(...point).project(camera);return[(p.x+1)*W/2,(1-p.y)*H/2];}
function dimension(show){const svg=document.getElementById('dimension');svg.style.display=show?'block':'none';if(!show)return;const a=project([.95,.4,1.15]),b=project([.95,0,1.15]);
 const l=document.getElementById('dimension-line');l.setAttribute('x1',a[0]);l.setAttribute('y1',a[1]);l.setAttribute('x2',b[0]);l.setAttribute('y2',b[1]);
 for(const [id,p]of[['tick-top',a],['tick-bottom',b]]){const o=document.getElementById(id);o.setAttribute('x1',p[0]-15);o.setAttribute('x2',p[0]+15);o.setAttribute('y1',p[1]);o.setAttribute('y2',p[1]);}
 const text=document.getElementById('dimension-text');text.setAttribute('x',(a[0]+b[0])/2-120);text.setAttribute('y',(a[1]+b[1])/2+8);
}
function setCamera(target,azimuth,elevation,height,hero){camera.clearViewOffset();camera.left=-height*16/9/2;camera.right=height*16/9/2;camera.top=height/2;camera.bottom=-height/2;const d=5;camera.position.set(target.x+Math.sin(azimuth)*Math.cos(elevation)*d,target.y+Math.sin(elevation)*d,target.z+Math.cos(azimuth)*Math.cos(elevation)*d);camera.lookAt(target);if(hero)camera.setViewOffset(W,H,225,0,W,H);camera.updateProjectionMatrix();camera.updateMatrixWorld();}

window.renderFrame=async function(t=0,mode='video'){
 const hero=mode==='hero'||t<3.5;const pose=hero?poseAt(0):poseAt(t);
 root.position.set(pose.x,pose.y,0);root.rotation.z=pose.pitch;seat.rotation.z=-pose.pitch;scene.updateMatrixWorld(true);rebuildActuator();supportLegs(pose);
 for(const g of trackGroups)g.userData.animate(-pose.travel);
 obstacle.visible=!hero&&t>=8.5;
 overlay.style.transform=`scale(${innerWidth/W},${innerHeight/H})`;
 overlay.className=hero?'':'video';
 if(hero){title.textContent='履带式辅助移动座椅';subtitle.textContent='支腿辅助方案 · 成品外观概念图';badge.textContent='外观候选 · 尚未验证';setCamera(new THREE.Vector3(0,.67,0),.73,.34,2.20,true);}
 else{
  title.textContent='RoboLaoye · 候选方案 A 动作示意';subtitle.textContent='履带底盘 + 四角辅助支腿 + 座椅俯仰调平';badge.textContent='构想演示 / 非运动学仿真';
  const p=phases[pose.phase];document.getElementById('phase').textContent=`${String(pose.phase).padStart(2,'0')}　${p[0]}`;document.getElementById('description').textContent=p[1];
  for(const o of document.querySelectorAll('.step')){const i=Number(o.dataset.i);o.className='step'+(i===Math.min(pose.phase,6)?' active':i<pose.phase?' done':'');}
  const az=t<8.5?.73+Math.sin((t-3.5)/5*Math.PI)*.34:t<12?.83:THREE.MathUtils.lerp(.83,.48,range(t,12,16));
  const endaz=t>30?.48+(t-30)*.06:az;const tx=t<8.5?pose.x+.08:THREE.MathUtils.lerp(.65,1.15,range(t,20,28));
  setCamera(new THREE.Vector3(tx,.78,0),endaz,.30,2.85,false);
 }
 dimension(!hero&&t>=8.5&&t<30);
 renderer.render(scene,camera);
 await new Promise(resolve=>requestAnimationFrame(resolve));
 return{time:t,mode:hero?'hero':'video',phase:pose.phase,triangles:renderer.info.render.triangles};
};
window.sceneInfo={candidate:'support_leg_assisted_tracks',duration:34,units:'metres',status:'concept_not_validated',webgl:renderer.getContext().getParameter(renderer.getContext().VERSION)};
window.resizeRender=function(width,height){renderer.setPixelRatio(1);renderer.setSize(width,height);};
await window.renderFrame(0,'hero');
window.sceneReady=true;
// For interactive inspection only: press space to play/pause, R to restart.
let playing=false,start=0,held=0;
addEventListener('keydown',e=>{if(e.code==='Space'){playing=!playing;start=performance.now()-held*1000;}if(e.code==='KeyR'){held=0;start=performance.now();}});
function preview(now){if(playing){held=Math.min(34,(now-start)/1000);window.renderFrame(held,'video');if(held>=34)playing=false;}requestAnimationFrame(preview);}requestAnimationFrame(preview);

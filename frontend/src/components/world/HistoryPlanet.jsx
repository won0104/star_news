import { useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import ConstellationCanvas from './ConstellationCanvas';
import styles from './HistoryPane.module.css';

/**
 * 개인 그래프 요약을 회전 가능한 3D 행성으로 그린다. Three.js는 고빈도 렌더링과
 * picking을 맡고, DOM 라벨·선택 패널은 키보드와 스크린 리더 접근성을 보완한다.
 */
const PLANET_RADIUS = 5;
const EDGE_SURFACE_OFFSET = 0.045;
const TOPIC_STAR_SCALE = 0.7;
const STANDARD_CAMERA = { minimum: 8.4, maximum: 14.2, defaultZ: 11.4 };
const DIARY_CAMERA = { minimum: 19.5, maximum: 28.2, defaultZ: 23.4 };
const LABEL_LIMIT = 12;
const MOBILE_LABEL_LIMIT = 8;
const EVENT_CARD_STAR_SCALE = 0.3;
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));
const FRONT = new THREE.Vector3(0, 0, 1);
const MODEL_FRONT = new THREE.Vector3(1, 0, 0);
/*
 * 별 모델. 인덱스를 uint32 에서 uint16 으로 줄인 판이다 — 정점이 10,769 개뿐이라 최대
 * 인덱스가 10,768 이고 uint16(65,535)에 여유롭게 들어간다. 같은 숫자를 좁은 칸에 담을
 * 뿐이라 형태는 바이트 단위로 같고 437KB 가 345KB 가 된다.
 *
 * public/ 아래 파일은 빌드 해시가 붙지 않으므로 갈아끼울 때는 이름을 올려야 한다 —
 * 같은 이름으로 덮으면 CDN 이 옛 바이트를 계속 내준다.
 */
const STAR_MODEL_URL = '/assets/history/star-node-v2.glb';

const TOPIC_COLORS = {
  POLITICS: 0xec8d9d,
  ECONOMY: 0xe7bc5b,
  SOCIETY: 0x80d7c1,
  CULTURE: 0xefb484,
  INTERNATIONAL: 0xc09bf4,
  SPORTS: 0x6fcde2,
  IT_SCIENCE: 0x7aa4ff,
};

const EVENT_SIZE_STEPS = [
  { maximum: 3, label: '1–3', size: 0.54 },
  { maximum: 6, label: '4–6', size: 0.68 },
  { maximum: 9, label: '7–9', size: 0.82 },
  { maximum: Number.POSITIVE_INFINITY, label: '10+', size: 0.94 },
];

/**
 * 행성 위의 노드는 두 종류다 — 분야(TOPIC_CLUSTER)와 사건(EVENT).
 *
 * 인물·기관과 발언은 올리지 않는다. 한 사건에 딸린 인물이 열 개를 넘는 일이 흔해서,
 * 구 표면이 이름표로 덮이고 정작 축이 되는 사건이 그 사이에 묻힌다. 둘은 사건을 고른 뒤
 * 오른쪽 페이지에서 본다 — 거기서는 목록이라 수가 늘어도 읽을 수 있다.
 *
 * 그래서 행성이 답하는 질문은 "어떤 분야에서 어떤 사건을 읽었나" 하나로 좁혀진다.
 * 색은 분야(topicCode), 크기는 읽은 기사 수가 쓴다.
 *
 * `sizeMultiplier` 는 기사 수로 정한 크기 위에 곱해진다.
 */
const NODE_STYLE = {
  TOPIC_CLUSTER: { label: '분야', sizeMultiplier: 1 },
  EVENT: { label: '사건', sizeMultiplier: 1 },
};

const RELATION_LABEL = {
  BELONGS_TO_TOPIC: '분야에 속함',
  CAUSES: '원인·결과',
  SUBEVENT_OF: '상위 사건',
  ACTOR: '주체',
  TARGET: '대상',
  CONTAINS_STATEMENT: '발언 포함',
  PART_OF: '상위 사건',
  OCCURRED_AT: '발생 시점',
};

const clamp = (value, minimum, maximum) => Math.max(minimum, Math.min(maximum, value));

function fallbackTopicPoint(index, count) {
  const y = 1 - ((index + 0.5) / Math.max(count, 1)) * 2;
  const horizontalRadius = Math.sqrt(Math.max(0, 1 - y * y));
  const angle = GOLDEN_ANGLE * index;
  return new THREE.Vector3(
    Math.cos(angle) * horizontalRadius,
    y,
    Math.sin(angle) * horizontalRadius,
  );
}

function buildLayout(graph) {
  // 분야와 사건만 행성에 세운다(위 NODE_STYLE 주석 참조). 인물·발언은 통과시키지 않으므로
  // 그들에게 걸린 Edge 도 함께 떨군다 — 남겨 두면 없는 노드로 향하는 선이 생긴다.
  const nodes = (graph.nodes ?? []).filter(
    (node) => node.kind === 'TOPIC_CLUSTER' || node.nodeType === 'EVENT',
  );
  const topics = nodes.filter((node) => node.kind === 'TOPIC_CLUSTER');
  const topicAnchors = new Map();

  const orderedTopics = [...topics].sort((left, right) => left.topicCode.localeCompare(right.topicCode));
  orderedTopics.forEach((topic, index) => {
    topicAnchors.set(topic.topicCode, fallbackTopicPoint(index, orderedTopics.length));
  });

  const childIndexes = new Map();
  const layoutNodes = nodes.map((node) => {
    const anchor = topicAnchors.get(node.topicCode) ?? fallbackTopicPoint(0, 1);
    if (node.kind === 'TOPIC_CLUSTER') {
      return { ...node, position: anchor.clone().multiplyScalar(PLANET_RADIUS + 0.18) };
    }

    const index = childIndexes.get(node.topicCode) ?? 0;
    childIndexes.set(node.topicCode, index + 1);
    const tangentA = new THREE.Vector3(0, 1, 0).cross(anchor);
    if (tangentA.lengthSq() < 0.01) tangentA.set(1, 0, 0);
    tangentA.normalize();
    const tangentB = anchor.clone().cross(tangentA).normalize();
    const ring = Math.floor(index / 6);
    const angle = index * GOLDEN_ANGLE;
    const spread = 0.18 + (index % 6) * 0.025 + ring * 0.1;
    const surfacePoint = anchor.clone()
      .addScaledVector(tangentA, Math.cos(angle) * spread)
      .addScaledVector(tangentB, Math.sin(angle) * spread)
      .normalize();
    const elevation = 0.12 + clamp(node.weight ?? 0.4, 0, 1) * 0.28;
    return { ...node, position: surfacePoint.multiplyScalar(PLANET_RADIUS + elevation) };
  });

  const kept = new Set(layoutNodes.map((node) => node.id));
  const edges = (graph.edges ?? []).filter(
    (edge) => kept.has(edge.sourceId) && kept.has(edge.targetId),
  );
  const adjacency = new Map(layoutNodes.map((node) => [node.id, new Set()]));
  edges.forEach((edge) => {
    if (!adjacency.has(edge.sourceId) || !adjacency.has(edge.targetId)) return;
    adjacency.get(edge.sourceId).add(edge.targetId);
    adjacency.get(edge.targetId).add(edge.sourceId);
  });

  return {
    nodes: layoutNodes,
    edges,
    nodeById: new Map(layoutNodes.map((node) => [node.id, node])),
    topicAnchors,
    adjacency,
  };
}

function trackballPoint(clientX, clientY, rect) {
  const scale = Math.max(1, Math.min(rect.width, rect.height));
  const x = ((clientX - rect.left) * 2 - rect.width) / scale;
  const y = (rect.height - (clientY - rect.top) * 2) / scale;
  const distanceSquared = x * x + y * y;
  if (distanceSquared <= 1) {
    return new THREE.Vector3(x, y, Math.sqrt(1 - distanceSquared));
  }
  const length = Math.sqrt(distanceSquared);
  return new THREE.Vector3(x / length, y / length, 0);
}

function makeArc(start, end) {
  const points = [];
  const normalizedStart = start.clone().normalize();
  const normalizedEnd = end.clone().normalize();

  for (let index = 0; index <= 32; index += 1) {
    const progress = index / 32;
    const point = normalizedStart.clone().lerp(normalizedEnd, progress).normalize();
    point.multiplyScalar(PLANET_RADIUS + EDGE_SURFACE_OFFSET);
    points.push(point);
  }
  return points;
}

function nodeKind(node) {
  return node.kind === 'TOPIC_CLUSTER' ? 'TOPIC_CLUSTER' : (node.nodeType ?? 'EVENT');
}

function colorForNode(node) {
  return TOPIC_COLORS[node.topicCode] ?? 0xe9f2f8;
}

function cssColorForNode(node) {
  return `#${colorForNode(node).toString(16).padStart(6, '0')}`;
}

function eventSizeForArticleCount(articleCount) {
  return EVENT_SIZE_STEPS.find((step) => articleCount <= step.maximum) ?? EVENT_SIZE_STEPS.at(-1);
}

function disposeObject(object) {
  object.traverse((child) => {
    child.geometry?.dispose();
    if (Array.isArray(child.material)) child.material.forEach((material) => material.dispose());
    else child.material?.dispose();
  });
}

export default function HistoryPlanet({
  graph,
  activeTopic,
  reduceMotion,
  selectedNode,
  selectedEvent,
  onSelectNode,
  onOpenEvent,
  variant = 'default',
  eventDisplay = 'star',
}) {
  const isDiary = variant === 'diary';
  const useEventCards = eventDisplay === 'card';
  const cameraConfig = isDiary ? DIARY_CAMERA : STANDARD_CAMERA;
  const layout = useMemo(() => buildLayout(graph), [graph]);
  const mountRef = useRef(null);
  const labelRefs = useRef(new Map());
  const onSelectRef = useRef(onSelectNode);
  const activeTopicRef = useRef(activeTopic);
  const selectedNodeRef = useRef(selectedNode);
  const autoRotateRef = useRef(!reduceMotion);
  const groupRef = useRef(null);
  const cameraRef = useRef(null);
  const focusRef = useRef(null);
  const focusTopicRef = useRef(() => {});
  const focusNodeRef = useRef(() => {});
  const targetCameraZRef = useRef(cameraConfig.defaultZ);
  const manualPauseUntilRef = useRef(0);
  const styleDirtyRef = useRef(true);
  const [zoomPercent, setZoomPercent] = useState(100);
  const [autoRotating, setAutoRotating] = useState(!reduceMotion);
  const [webglUnavailable, setWebglUnavailable] = useState(false);

  useEffect(() => {
    onSelectRef.current = onSelectNode;
  }, [onSelectNode]);

  useEffect(() => {
    autoRotateRef.current = !reduceMotion && autoRotating;
  }, [autoRotating, reduceMotion]);

  useEffect(() => {
    activeTopicRef.current = activeTopic;
    styleDirtyRef.current = true;
  }, [activeTopic]);

  useEffect(() => {
    selectedNodeRef.current = selectedNode;
    styleDirtyRef.current = true;
  }, [selectedNode]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    } catch {
      window.setTimeout(() => setWebglUnavailable(true), 0);
      return undefined;
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.className = styles.planetCanvas;
    renderer.domElement.setAttribute('aria-hidden', 'true');
    mount.prepend(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x081018, 0.025);
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 80);
    camera.position.set(0, 0, targetCameraZRef.current);
    cameraRef.current = camera;

    const globe = new THREE.Group();
    groupRef.current = globe;
    scene.add(globe);

    const planetGeometry = new THREE.SphereGeometry(PLANET_RADIUS, 72, 48);
    const planetMaterial = new THREE.MeshStandardMaterial({
      color: 0x0b1721,
      roughness: 0.82,
      metalness: 0.08,
      emissive: 0x08121b,
      emissiveIntensity: 0.55,
    });
    const planet = new THREE.Mesh(planetGeometry, planetMaterial);
    globe.add(planet);

    const grid = new THREE.Mesh(
      new THREE.SphereGeometry(PLANET_RADIUS + 0.035, 36, 24),
      new THREE.MeshBasicMaterial({
        color: 0x87a9bd,
        wireframe: true,
        transparent: true,
        opacity: 0.038,
      }),
    );
    globe.add(grid);

    // 대기 광채 구체(반지름 +0.32, BackSide)를 걷어냈다. 안쪽 면만 그려 테두리만 남는
    // 방식이라 행성을 감싸는 빛이 아니라 행성 밖에 그려진 원 하나로 읽혔다.

    scene.add(new THREE.HemisphereLight(0xb8d9ed, 0x05080c, 1.35));
    const keyLight = new THREE.DirectionalLight(0xdcecf6, 2.4);
    keyLight.position.set(-5, 7, 9);
    scene.add(keyLight);
    const rimLight = new THREE.PointLight(0x6ba9d0, 18, 28, 2);
    rimLight.position.set(7, -4, 7);
    scene.add(rimLight);

    let disposed = false;
    const nodeEntries = new Map();
    const pickMeshes = [];
    const edgeEntries = [];

    layout.nodes.forEach((node, nodeIndex) => {
      const isTopic = node.kind === 'TOPIC_CLUSTER';
      const kind = nodeKind(node);
      const style = NODE_STYLE[kind] ?? NODE_STYLE.EVENT;
      const sizeStep = eventSizeForArticleCount(node.sourceArticleCount);
      const modelSize = (isTopic ? 0.94 : sizeStep.size * 0.76) * style.sizeMultiplier;
      const holder = new THREE.Group();
      holder.position.copy(node.position);
      holder.userData.nodeId = node.id;

      const modelHolder = new THREE.Group();
      modelHolder.quaternion.setFromUnitVectors(MODEL_FRONT, node.position.clone().normalize());
      modelHolder.rotateX(nodeIndex * GOLDEN_ANGLE);
      holder.add(modelHolder);

      // 시각 크기와 클릭 영역을 분리해 작은 3D 코어도 편하게 선택할 수 있게 한다.
      const pickMesh = new THREE.Mesh(
        new THREE.SphereGeometry(1, 12, 8),
        new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }),
      );
      pickMesh.scale.setScalar(modelSize * 0.54);
      pickMesh.userData.nodeId = node.id;
      holder.add(pickMesh);
      pickMeshes.push(pickMesh);

      globe.add(holder);

      // 분야와 사건 둘 다 별 모델(glb)을 쓴다 — 아래 GLTFLoader 가 채운다.
      let model = null;
      let modelMaterial = null;

      nodeEntries.set(node.id, {
        node,
        kind,
        holder,
        modelHolder,
        model,
        modelMaterial,
        baseModelSize: modelSize,
        baseModelScale: 1,
      });
    });

    new GLTFLoader().load(STAR_MODEL_URL, (gltf) => {
      if (disposed) {
        disposeObject(gltf.scene);
        return;
      }

      gltf.scene.updateMatrixWorld(true);
      const bounds = new THREE.Box3().setFromObject(gltf.scene);
      const center = bounds.getCenter(new THREE.Vector3());
      const dimensions = bounds.getSize(new THREE.Vector3());
      const maximumDimension = Math.max(dimensions.x, dimensions.y, dimensions.z) || 1;

      nodeEntries.forEach((entry) => {
        if (entry.model) return;
        const color = colorForNode(entry.node);
        const isTopic = entry.node.kind === 'TOPIC_CLUSTER';
        const isCompactEvent = useEventCards && entry.kind === 'EVENT';
        const material = new THREE.MeshStandardMaterial({
          color,
          emissive: color,
          emissiveIntensity: isTopic ? 0.42 : (isCompactEvent ? 0.48 : 0.24),
          roughness: 0.4,
          metalness: 0.1,
          transparent: true,
        });
        const model = gltf.scene.clone(true);
        model.position.sub(center);
        model.traverse((child) => {
          if (child.isMesh) child.material = material;
        });
        const modelScale = (entry.baseModelSize / maximumDimension)
          * (isCompactEvent ? EVENT_CARD_STAR_SCALE : 1);
        model.scale.setScalar(modelScale);
        entry.modelHolder.add(model);
        entry.model = model;
        entry.modelMaterial = material;
        entry.baseModelScale = modelScale;
      });
      styleDirtyRef.current = true;
    }, undefined, () => {
      // 네트워크 실패 시 라벨과 선택 기능은 유지하고 모델만 비워둔다.
    });

    layout.edges.forEach((edge) => {
      const source = layout.nodeById.get(edge.sourceId);
      const target = layout.nodeById.get(edge.targetId);
      if (!source || !target || source.id === target.id) return;
      const geometry = new THREE.BufferGeometry().setFromPoints(makeArc(source.position, target.position));
      const color = colorForNode(source);
      const material = new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity: 0.13 + clamp(edge.weight ?? 0.4, 0, 1) * 0.18,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      });
      const line = new THREE.Line(geometry, material);
      globe.add(line);
      edgeEntries.push({ edge, material, source, target, color });
    });

    const queueFocus = (direction, immediate = false) => {
      if (!direction) return;
      const target = new THREE.Quaternion().setFromUnitVectors(direction.clone().normalize(), FRONT);
      if (immediate || reduceMotion) {
        globe.quaternion.copy(target);
        focusRef.current = null;
      } else {
        focusRef.current = {
          from: globe.quaternion.clone(),
          to: target,
          startedAt: performance.now(),
          duration: 780,
        };
      }
    };

    focusTopicRef.current = (topicCode, immediate = false) => {
      queueFocus(layout.topicAnchors.get(topicCode), immediate);
    };
    focusNodeRef.current = (nodeId, immediate = false) => {
      queueFocus(layout.nodeById.get(nodeId)?.position, immediate);
    };

    if (selectedNodeRef.current?.id) focusNodeRef.current(selectedNodeRef.current.id, true);
    else focusTopicRef.current(activeTopicRef.current, true);

    const applyEmphasis = () => {
      const currentTopic = activeTopicRef.current;
      const currentSelection = selectedNodeRef.current?.id;
      const neighbors = currentSelection ? (layout.adjacency.get(currentSelection) ?? new Set()) : new Set();
      nodeEntries.forEach((entry) => {
        const inTopic = entry.node.topicCode === currentTopic;
        const isTopic = entry.node.kind === 'TOPIC_CLUSTER';
        const isSelected = entry.node.id === currentSelection;
        const isNeighbor = neighbors.has(entry.node.id);
        let sizeMultiplier;
        if (currentSelection) {
          if (entry.modelMaterial) {
            entry.modelMaterial.opacity = isSelected || isNeighbor ? 1 : 0.12;
            entry.modelMaterial.emissiveIntensity = isSelected ? 0.72 : (isNeighbor ? 0.36 : 0.06);
          }
          sizeMultiplier = isSelected ? 1.15 : (isNeighbor ? 1.04 : 0.9);
        } else {
          if (entry.modelMaterial) {
            entry.modelMaterial.opacity = isTopic || inTopic ? 1 : 0.2;
            entry.modelMaterial.emissiveIntensity = isTopic ? 0.42 : (inTopic ? 0.24 : 0.06);
          }
          sizeMultiplier = isTopic || inTopic ? 1 : 0.92;
        }
        if (isTopic) sizeMultiplier = TOPIC_STAR_SCALE;
        entry.model?.scale.setScalar(entry.baseModelScale * sizeMultiplier);
      });
      edgeEntries.forEach((entry) => {
        const connected = entry.edge.sourceId === currentSelection || entry.edge.targetId === currentSelection;
        const inTopic = entry.source.topicCode === currentTopic || entry.target.topicCode === currentTopic;
        entry.material.color.setHex(entry.color);
        entry.material.opacity = currentSelection
          ? (connected ? 0.68 + clamp(entry.edge.weight ?? 0.4, 0, 1) * 0.22 : 0.012)
          : (inTopic ? 0.2 + clamp(entry.edge.weight ?? 0.4, 0, 1) * 0.26 : 0.025);
      });
      styleDirtyRef.current = false;
    };

    const resize = () => {
      const rect = mount.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      renderer.setSize(rect.width, rect.height, false);
      camera.aspect = rect.width / rect.height;
      camera.updateProjectionMatrix();
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(mount);
    resize();

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const drag = {
      active: false,
      pointerId: null,
      startX: 0,
      startY: 0,
      lastPoint: new THREE.Vector3(),
      lastTime: 0,
      moved: false,
    };
    const momentum = { axis: new THREE.Vector3(0, 1, 0), speed: 0 };
    const deltaQuaternion = new THREE.Quaternion();

    const applyScreenRotation = (axis, angle) => {
      deltaQuaternion.setFromAxisAngle(axis, angle);
      globe.quaternion.premultiply(deltaQuaternion).normalize();
    };

    const rotateTrackball = (from, to, elapsedSeconds) => {
      deltaQuaternion.setFromUnitVectors(from, to);
      globe.quaternion.premultiply(deltaQuaternion).normalize();

      const angle = 2 * Math.acos(clamp(deltaQuaternion.w, -1, 1));
      const sinHalfAngle = Math.sqrt(Math.max(0, 1 - deltaQuaternion.w * deltaQuaternion.w));
      if (angle < 0.001 || sinHalfAngle < 0.001) return;
      const axis = new THREE.Vector3(
        deltaQuaternion.x / sinHalfAngle,
        deltaQuaternion.y / sinHalfAngle,
        deltaQuaternion.z / sinHalfAngle,
      ).normalize();
      momentum.axis.lerp(axis, 0.62).normalize();
      momentum.speed = clamp(angle / Math.max(elapsedSeconds, 0.012), 0, 3.2);
    };

    const handlePointerDown = (event) => {
      if (event.button !== 0) return;
      focusRef.current = null;
      manualPauseUntilRef.current = Number.POSITIVE_INFINITY;
      drag.active = true;
      drag.pointerId = event.pointerId;
      drag.startX = event.clientX;
      drag.startY = event.clientY;
      drag.lastPoint.copy(trackballPoint(event.clientX, event.clientY, renderer.domElement.getBoundingClientRect()));
      drag.lastTime = performance.now();
      drag.moved = false;
      momentum.speed = 0;
      renderer.domElement.setPointerCapture(event.pointerId);
    };

    const handlePointerMove = (event) => {
      if (!drag.active || drag.pointerId !== event.pointerId) return;
      const now = performance.now();
      if (Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) > 6) drag.moved = true;
      const currentPoint = trackballPoint(event.clientX, event.clientY, renderer.domElement.getBoundingClientRect());
      rotateTrackball(drag.lastPoint, currentPoint, (now - drag.lastTime) / 1000);
      drag.lastPoint.copy(currentPoint);
      drag.lastTime = now;
    };

    const selectAt = (event) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(pickMeshes, false)[0];
      if (!hit) {
        onSelectRef.current(null);
        return;
      }
      const entry = nodeEntries.get(hit.object.userData.nodeId);
      if (!entry) return;
      const worldPosition = new THREE.Vector3();
      entry.holder.getWorldPosition(worldPosition);
      if (worldPosition.z < -0.2) {
        onSelectRef.current(null);
        return;
      }
      onSelectRef.current(entry.node);
    };

    const handlePointerUp = (event) => {
      if (!drag.active || drag.pointerId !== event.pointerId) return;
      if (renderer.domElement.hasPointerCapture(event.pointerId)) {
        renderer.domElement.releasePointerCapture(event.pointerId);
      }
      if (!drag.moved) selectAt(event);
      if (reduceMotion) momentum.speed = 0;
      drag.active = false;
      drag.pointerId = null;
      manualPauseUntilRef.current = selectedNodeRef.current
        ? Number.POSITIVE_INFINITY
        : performance.now() + 2600;
    };

    const setCameraDistance = (nextDistance) => {
      targetCameraZRef.current = clamp(nextDistance, cameraConfig.minimum, cameraConfig.maximum);
      const percent = Math.round((cameraConfig.defaultZ / targetCameraZRef.current) * 100);
      setZoomPercent(percent);
    };

    const handleWheel = (event) => {
      event.preventDefault();
      setCameraDistance(targetCameraZRef.current + event.deltaY * 0.0045);
    };

    const handleKeyDown = (event) => {
      const step = 0.11;
      let interruptsFocus = false;
      if (event.key === 'ArrowLeft') {
        applyScreenRotation(new THREE.Vector3(0, 1, 0), -step);
        interruptsFocus = true;
      } else if (event.key === 'ArrowRight') {
        applyScreenRotation(new THREE.Vector3(0, 1, 0), step);
        interruptsFocus = true;
      } else if (event.key === 'ArrowUp') {
        applyScreenRotation(new THREE.Vector3(1, 0, 0), -step);
        interruptsFocus = true;
      } else if (event.key === 'ArrowDown') {
        applyScreenRotation(new THREE.Vector3(1, 0, 0), step);
        interruptsFocus = true;
      }
      else if (event.key === '+' || event.key === '=') setCameraDistance(targetCameraZRef.current - 0.65);
      else if (event.key === '-') setCameraDistance(targetCameraZRef.current + 0.65);
      else if (event.key === 'Home') {
        focusTopicRef.current(activeTopicRef.current);
        momentum.speed = 0;
      }
      else if (event.key === 'Escape') {
        onSelectRef.current(null);
        focusRef.current = null;
        momentum.speed = 0;
      }
      else if (event.key === ' ') {
        setAutoRotating((current) => !current);
        manualPauseUntilRef.current = selectedNodeRef.current
          ? Number.POSITIVE_INFINITY
          : 0;
      } else return;
      if (interruptsFocus) {
        focusRef.current = null;
        momentum.speed = 0;
      }
      if (event.key !== ' ') {
        manualPauseUntilRef.current = selectedNodeRef.current
          ? Number.POSITIVE_INFINITY
          : performance.now() + 2600;
      }
      event.preventDefault();
    };

    renderer.domElement.addEventListener('pointerdown', handlePointerDown);
    renderer.domElement.addEventListener('pointermove', handlePointerMove);
    renderer.domElement.addEventListener('pointerup', handlePointerUp);
    renderer.domElement.addEventListener('pointercancel', handlePointerUp);
    renderer.domElement.addEventListener('wheel', handleWheel, { passive: false });
    mount.addEventListener('keydown', handleKeyDown);

    let frameId;
    let previousTime = performance.now();
    const worldPosition = new THREE.Vector3();
    const projected = new THREE.Vector3();
    const hiddenLabel = (element) => {
      element.style.opacity = '0';
      element.style.pointerEvents = 'none';
      element.tabIndex = -1;
      element.setAttribute('aria-hidden', 'true');
    };

    const updateLabels = () => {
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      const horizontalInset = width < 720 ? 72 : 104;
      const topInset = width < 720 ? 118 : 58;
      const bottomInset = width < 720 ? 126 : 58;
      const selectedId = selectedNodeRef.current?.id;
      const neighbors = selectedId ? (layout.adjacency.get(selectedId) ?? new Set()) : new Set();
      const isFar = camera.position.z > 12.7;
      const isMiddleDistance = camera.position.z > 11.8;
      const candidates = [];
      nodeEntries.forEach((entry) => {
        const isTopic = entry.node.kind === 'TOPIC_CLUSTER';
        const isCard = useEventCards && entry.kind === 'EVENT';
        if (isCard) entry.modelHolder.visible = true;
        const element = labelRefs.current.get(entry.node.id);
        if (!element) return;
        entry.holder.getWorldPosition(worldPosition);
        projected.copy(worldPosition).project(camera);
        const inTopic = entry.node.topicCode === activeTopicRef.current;
        const isSelected = entry.node.id === selectedId;
        const isNeighbor = neighbors.has(entry.node.id);
        const weight = clamp(entry.node.weight ?? 0.4, 0, 1);
        const onFront = worldPosition.z > -0.25 && projected.z < 1;
        const inViewport = Math.abs(projected.x) < 1.08 && Math.abs(projected.y) < 1.08;
        const passesLevelOfDetail = selectedId
          ? (isSelected || isNeighbor)
          : (isTopic || (inTopic && !isFar && (!isMiddleDistance || weight >= 0.56)));
        if (onFront && inViewport && passesLevelOfDetail) {
          candidates.push({
            id: entry.node.id,
            entry,
            isTopic,
            isCard,
            element,
            x: clamp((projected.x * 0.5 + 0.5) * width, horizontalInset, width - horizontalInset),
            y: clamp((-projected.y * 0.5 + 0.5) * height, topInset, height - bottomInset),
            depth: worldPosition.z,
            priority: (isSelected ? 100 : 0)
              + (isNeighbor ? 40 : 0)
              + (inTopic ? 20 : 0)
              + (isTopic ? 10 : 0),
          });
        } else {
          hiddenLabel(element);
        }
      });

      const limit = width < 720 ? MOBILE_LABEL_LIMIT : LABEL_LIMIT;
      candidates.sort((a, b) => (b.priority - a.priority) || (b.depth - a.depth));
      const occupied = [];
      let visibleCount = 0;
      candidates.forEach((candidate) => {
        const labelWidth = clamp(candidate.element.offsetWidth || 132, 88, 220);
        const labelHeight = clamp(candidate.element.offsetHeight || 38, 30, 64);
        const bounds = {
          left: candidate.x - labelWidth / 2 - 6,
          right: candidate.x + labelWidth / 2 + 6,
          top: candidate.y - labelHeight / 2 - 5,
          bottom: candidate.y + labelHeight / 2 + 5,
        };
        const overlaps = occupied.some((other) => (
          bounds.left < other.right
          && bounds.right > other.left
          && bounds.top < other.bottom
          && bounds.bottom > other.top
        ));
        const visible = visibleCount < limit && (!overlaps || candidate.priority >= 100);
        candidate.element.style.zIndex = String(Math.round(300 + candidate.depth * 10));
        candidate.element.style.transform = `translate3d(${candidate.x}px, ${candidate.y}px, 0) translate(-50%, -50%)`;
        if (!visible) {
          hiddenLabel(candidate.element);
          return;
        }
        candidate.element.style.opacity = '1';
        candidate.element.style.pointerEvents = 'auto';
        candidate.element.tabIndex = 0;
        candidate.element.setAttribute('aria-hidden', 'false');
        if (candidate.isCard) candidate.entry.modelHolder.visible = false;
        occupied.push(bounds);
        visibleCount += 1;
      });
    };

    const animate = (now) => {
      const elapsedSeconds = clamp((now - previousTime) / 1000, 0, 0.05);
      previousTime = now;
      if (styleDirtyRef.current) applyEmphasis();

      const zoomEase = 1 - Math.exp(-10 * elapsedSeconds);
      camera.position.z += (targetCameraZRef.current - camera.position.z) * zoomEase;

      if (focusRef.current) {
        momentum.speed = 0;
        const focus = focusRef.current;
        const progress = clamp((now - focus.startedAt) / focus.duration, 0, 1);
        const eased = 1 - ((1 - progress) ** 3);
        globe.quaternion.slerpQuaternions(focus.from, focus.to, eased);
        if (progress >= 1) focusRef.current = null;
      } else if (!drag.active) {
        if (!reduceMotion && momentum.speed > 0.002) {
          applyScreenRotation(momentum.axis, momentum.speed * elapsedSeconds);
          momentum.speed *= Math.exp(-4.6 * elapsedSeconds);
        }
        const autoRotationAvailable = now >= manualPauseUntilRef.current;
        if (autoRotateRef.current && autoRotationAvailable && momentum.speed < 0.012) {
          applyScreenRotation(new THREE.Vector3(0, 1, 0), 0.042 * elapsedSeconds);
        }
      }

      globe.updateMatrixWorld(true);
      updateLabels();
      renderer.render(scene, camera);
      frameId = requestAnimationFrame(animate);
    };
    frameId = requestAnimationFrame(animate);

    return () => {
      disposed = true;
      cancelAnimationFrame(frameId);
      resizeObserver.disconnect();
      renderer.domElement.removeEventListener('pointerdown', handlePointerDown);
      renderer.domElement.removeEventListener('pointermove', handlePointerMove);
      renderer.domElement.removeEventListener('pointerup', handlePointerUp);
      renderer.domElement.removeEventListener('pointercancel', handlePointerUp);
      renderer.domElement.removeEventListener('wheel', handleWheel);
      mount.removeEventListener('keydown', handleKeyDown);
      disposeObject(scene);
      renderer.dispose();
      renderer.domElement.remove();
      groupRef.current = null;
      cameraRef.current = null;
      focusTopicRef.current = () => {};
      focusNodeRef.current = () => {};
    };
  }, [cameraConfig, layout, reduceMotion, useEventCards]);

  useEffect(() => {
    focusTopicRef.current(activeTopic);
    manualPauseUntilRef.current = performance.now() + 4200;
  }, [activeTopic]);

  useEffect(() => {
    if (selectedNode?.id) {
      focusNodeRef.current(selectedNode.id);
      manualPauseUntilRef.current = Number.POSITIVE_INFINITY;
    } else {
      manualPauseUntilRef.current = performance.now() + 2600;
    }
  }, [selectedNode]);

  const changeZoom = (amount) => {
    if (!cameraRef.current) return;
    targetCameraZRef.current = clamp(
      targetCameraZRef.current + amount,
      cameraConfig.minimum,
      cameraConfig.maximum,
    );
    setZoomPercent(Math.round((cameraConfig.defaultZ / targetCameraZRef.current) * 100));
  };

  const selectedRelations = selectedNode
    ? layout.edges
      .filter((edge) => edge.sourceId === selectedNode.id || edge.targetId === selectedNode.id)
      .map((edge) => {
        const outgoing = edge.sourceId === selectedNode.id;
        return {
          node: layout.nodeById.get(outgoing ? edge.targetId : edge.sourceId),
          relationship: edge.relationship,
          direction: outgoing ? '→' : '←',
        };
      })
      .filter((relation) => relation.node)
      .sort((a, b) => Number(a.relationship === 'BELONGS_TO_TOPIC') - Number(b.relationship === 'BELONGS_TO_TOPIC'))
    : [];

  return (
    <div className={`${styles.planetFrame} ${isDiary ? styles.diaryPlanetFrame : ''} ${useEventCards ? styles.eventCardMode : ''}`}>
      {/* 다이어리에서도 범례를 둔다 — 모양이 유형을 뜻한다는 것을 말해줄 자리가 여기뿐이고,
          모양은 색처럼 짐작되지 않는다. 좁은 인셋이라 크기와 자리만 줄인다. */}
      <div
        className={`${styles.planetLegend} ${isDiary ? styles.diaryLegend : ''}`}
        aria-label="노드 범례"
      >
        {Object.entries(NODE_STYLE).map(([kind, item]) => (
          <span key={kind} className={styles.legendItem}>
            <i data-node-kind={kind} aria-hidden="true" />
            {item.label}
          </span>
        ))}
      </div>

      {!isDiary && !useEventCards && <div
        className={styles.planetScale}
        aria-label="이벤트 별 크기. 읽은 기사 1에서 3개, 4에서 6개, 7에서 9개, 10개 이상 순으로 커집니다."
      >
        <span>기사 수</span>
        {EVENT_SIZE_STEPS.map((step, index) => (
          <span key={step.label}>
            <i style={{ '--scale-star': `${7 + index * 2}px` }} aria-hidden="true" />
            {step.label}
          </span>
        ))}
      </div>}

      <div
        ref={mountRef}
        className={`${styles.planetViewport} ${isDiary ? styles.diaryPlanetViewport : ''}`}
        role="application"
        tabIndex={0}
        aria-label="나의 기록 3D 행성. 드래그하거나 방향키로 회전하고, 마우스 휠이나 더하기와 빼기 키로 확대할 수 있습니다."
      >
        <ConstellationCanvas reduceMotion={reduceMotion} />

        {!webglUnavailable && (
          <div className={styles.planetLabels}>
            {layout.nodes.map((node) => (
              <button
                key={node.id}
                ref={(element) => {
                  if (element) labelRefs.current.set(node.id, element);
                  else labelRefs.current.delete(node.id);
                }}
                type="button"
                className={styles.planetLabel}
                data-node-kind={nodeKind(node)}
                style={{ '--node-color': cssColorForNode(node) }}
                aria-pressed={selectedNode?.id === node.id}
                aria-hidden="true"
                tabIndex={-1}
                onClick={() => onSelectNode(node)}
              >
                <strong>{node.title}</strong>
                {/* 기사 수가 없으면(분야 칸 등) 대신 자기 유형을 밝힌다. */}
                <small>
                  {node.sourceArticleCount == null
                    ? (NODE_STYLE[nodeKind(node)] ?? NODE_STYLE.EVENT).label
                    : `${node.sourceArticleCount}개 기사`}
                </small>
              </button>
            ))}
          </div>
        )}

        {webglUnavailable && (
          <div className={styles.webglFallback}>
            <strong>이 환경에서는 3D 지도를 표시할 수 없어요.</strong>
            <p>아래 목록에서 기록 노드를 선택할 수 있습니다.</p>
            <div>
              {layout.nodes.filter((node) => node.topicCode === activeTopic).map((node) => (
                <button key={node.id} type="button" onClick={() => onSelectNode(node)}>{node.title}</button>
              ))}
            </div>
          </div>
        )}

        {!isDiary && <div className={styles.planetControls} aria-label="지도 확대/축소">
          <button type="button" onClick={() => changeZoom(0.65)} aria-label="축소">−</button>
          <span>{zoomPercent}%</span>
          <button type="button" onClick={() => changeZoom(-0.65)} aria-label="확대">＋</button>
        </div>}

        {!isDiary && <p className={styles.planetHint}>
          구면을 잡아 돌리기 · 휠 확대 · 빈 곳을 누르면 선택 해제
          {!reduceMotion && (selectedNode
            ? ' · 선택 중 자동 회전 정지'
            : ` · SPACE ${autoRotating ? 'PAUSE' : 'PLAY'}`)}
        </p>}

        {!isDiary && selectedNode && selectedEvent && (
          <aside className={styles.eventArticlesPanel} aria-live="polite" aria-labelledby="selected-event-title">
            <div className={styles.eventArticlesHead}>
              <div>
                <span>RELATED ARTICLES</span>
                <h3 id="selected-event-title">{selectedEvent.title}</h3>
              </div>
              <button
                type="button"
                className={styles.clearSelection}
                aria-label="이벤트 기사 창 닫기"
                onClick={() => onSelectNode(null)}
              >
                ×
              </button>
            </div>
            <p className={styles.eventArticlesMeta}>
              관련 기사 {selectedEvent.articles.length}개 · 마지막 열람 {selectedEvent.lastReadAt}
            </p>
            <ul className={styles.eventArticleList}>
              {selectedEvent.articles.map((article, index) => (
                <li key={article.id}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <div>
                    <small>{article.source} · {article.readAt}</small>
                    <strong>{article.title}</strong>
                    <p>{article.summary}</p>
                  </div>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className={styles.openEventButton}
              onClick={() => onOpenEvent(selectedNode)}
            >
              이벤트 상세에서 기사 보기 →
            </button>
          </aside>
        )}

        {!isDiary && selectedNode && !selectedEvent && (
          <aside className={styles.nodeInspector} aria-live="polite">
            <div className={styles.nodeInspectorHead}>
              <span>
                {(NODE_STYLE[nodeKind(selectedNode)] ?? NODE_STYLE.EVENT).label}
                {selectedNode.isMock ? ' · MOCK' : ''}
              </span>
              <button
                type="button"
                className={styles.clearSelection}
                aria-label="노드 선택 해제"
                onClick={() => onSelectNode(null)}
              >
                ×
              </button>
            </div>
            <h3>{selectedNode.title}</h3>
            <p>
              직접 연결 {selectedRelations.length}개
              {selectedNode.sourceArticleCount != null
                && ` · 읽은 기사 ${selectedNode.sourceArticleCount}개`}
            </p>
            {selectedRelations.length > 0 && (
              <ul className={styles.nodeRelations} aria-label="직접 연결된 노드">
                {selectedRelations.slice(0, 3).map((relation) => (
                  <li key={`${relation.direction}:${relation.relationship}:${relation.node.id}`}>
                    <b>{relation.direction} {RELATION_LABEL[relation.relationship] ?? relation.relationship}</b>
                    {relation.node.title}
                  </li>
                ))}
                {selectedRelations.length > 3 && <li>외 {selectedRelations.length - 3}개</li>}
              </ul>
            )}
            {selectedNode.localContext && (
              <button type="button" onClick={() => onOpenEvent(selectedNode)}>읽은 기사 보기 →</button>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}

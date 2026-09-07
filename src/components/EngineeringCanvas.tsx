import project from "@/data/demo-project.json";

export { project };

/** Coordinates and routes come from the completed prototype, in metres/y-up. */
export function EngineeringCanvas({ stage = 3 }: { stage?: number }) {
  const point = (pos: number[]) => [pos[0] / project.scale, project.height - pos[1] / project.scale];
  return <svg className="engineering-canvas" viewBox={`0 0 ${project.width} ${project.height}`} role="img" aria-label="Actual architectural plan with generated electrical components and architecture-aware routes">
    <image href="/product/electrical-input.png" width={project.width} height={project.height}/>
    <g className={`engineering-layer room-layer ${stage >= 1 ? "shown" : ""}`}>{project.rooms.map(room => <rect key={room.id} x={room.x / project.scale} y={project.height - (room.y + room.height) / project.scale} width={room.width / project.scale} height={room.height / project.scale}/>)}</g>
    <g className={`engineering-layer route-layer ${stage >= 2 ? "shown" : ""}`}>{project.routes.map((route,index) => <polyline key={index} pathLength="1" points={route.waypoints.map(point).map(p => p.join(",")).join(" ")}/>)}</g>
    <g className={`engineering-layer component-layer ${stage >= 1 ? "shown" : ""}`}>{project.components.map(component => {
      const [x,y] = point(component.pos);
      return <g key={component.id} transform={`translate(${x} ${y})`}><title>{component.label}</title>{component.comp_id === "db" ? <rect x="-7" y="-7" width="14" height="14" rx="2"/> : <circle r="5"/>}<text y="2.5">{component.symbol.slice(0,1).toUpperCase()}</text></g>;
    })}</g>
  </svg>;
}

(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.GISInput=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  const clamp=(n,min,max)=>Math.max(min,Math.min(max,n));
  function tillerFromDrag(startX,currentX){
    const travel=clamp((currentX-startX)/170,-1,1);
    // The handle follows the mouse; the bow turns opposite the tiller.
    return travel===0?0:-Math.sign(travel)*Math.abs(travel)**1.5;
  }
  function sheetFromWheel(current,deltaY){return clamp(current-clamp(deltaY/100,-2,2)*.065,0,1)}
  return {tillerFromDrag,sheetFromWheel};
});

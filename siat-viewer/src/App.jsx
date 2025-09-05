// // src/App.jsx
// import React, { useState, useEffect } from "react";
// import OpenSlideViewer from "./components/OpenSlideViewer";
// import CzirwViewer from "./components/CziViewer";

// export default function App() {
//   const [canUseOpenSlide, setCanUseOpenSlide] = useState(false);
//   useEffect(() => {
//     fetch('http://127.0.0.1:5000/osd/dzi')
//       .then(r => setCanUseOpenSlide(r.ok))
//       .catch(() => setCanUseOpenSlide(false));
//   }, []);
  
//   return (
//   <div style={{width:'100%', height:'100vh', position:'relative'}}>
//     <CzirwViewer />
//     {canUseOpenSlide && (
//       <div style={{position:'absolute', inset:0, zIndex:2}}>
//         <OpenSlideViewer />
//       </div>
//     )}
//   </div>
// );
// }


// src/App.jsx
import './App.css';
import CzirwViewer from './components/CziViewer';

export default function App() {
  return (
    <div className="osd-shell">
      <CzirwViewer />
    </div>
  );
}

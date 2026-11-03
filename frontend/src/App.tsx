import { Route, Routes } from 'react-router-dom'
import { Nav } from './components/Chrome'
import Countries from './pages/Countries'
import Country from './pages/Country'
import Home from './pages/Home'
import Method from './pages/Method'
import Place from './pages/Place'

export default function App() {
  return (
    <>
      <Nav />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/methode" element={<Method />} />
        <Route path="/lieu/:id" element={<Place />} />
        <Route path="/pays" element={<Countries />} />
        <Route path="/pays/:id" element={<Country />} />
      </Routes>
    </>
  )
}

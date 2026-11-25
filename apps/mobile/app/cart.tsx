import { router } from 'expo-router';
import { Button, Empty, Page, Copy } from '../src/components/ui';
export default function Cart() {
  return <Page><Empty label="Your cart / not connected" title="Nothing added. Nothing assumed."
    message="Cart items and cart storage aren’t available yet. Your wishlist is a separate collection." />
    <Copy>DRIP checkout, orders and payments are not available. Eligible products may link to an approved retailer, where their own terms and sign-in apply.</Copy>
    <Button title="Continue discovering" onPress={() => router.navigate('/discover')} />
    <Button title="Checkout unavailable" disabled /></Page>;
}

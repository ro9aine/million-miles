import { CarDetailPage } from "../../../components/car-detail-page";


type Props = {
  params: {
    id: string;
  };
};


export default function CarRoute({ params }: Props) {
  return <CarDetailPage listingId={params.id} />;
}

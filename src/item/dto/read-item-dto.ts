import { CreateItemDto } from 'src/item/dto/create-item-dto';

export class ReadItemDto extends CreateItemDto {
  itemId: number;
}

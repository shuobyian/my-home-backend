import { Column, Entity, PrimaryGeneratedColumn } from 'typeorm';

@Entity('market', { schema: 'public' })
export class Market {
  @PrimaryGeneratedColumn({ type: 'integer', name: 'id' })
  id: number;

  @Column('varchar', { unique: true, name: 'name', length: 255 })
  name: string;

  @Column('integer', { name: 'price' })
  price: number;
}
